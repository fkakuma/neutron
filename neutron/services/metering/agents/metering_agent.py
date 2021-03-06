# Copyright (C) 2013 eNovance SAS <licensing@enovance.com>
#
# Author: Sylvain Afchain <sylvain.afchain@enovance.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import time

import eventlet
from oslo.config import cfg

from neutron.agent.common import config
from neutron.agent import rpc as agent_rpc
from neutron.common import constants as constants
from neutron.common import topics
from neutron.common import utils
from neutron import context
from neutron import manager
from neutron.openstack.common import importutils
from neutron.openstack.common import log as logging
from neutron.openstack.common import loopingcall
from neutron.openstack.common.notifier import api as notifier_api
from neutron.openstack.common import periodic_task
from neutron.openstack.common.rpc import proxy
from neutron.openstack.common import service
from neutron import service as neutron_service


LOG = logging.getLogger(__name__)


class MeteringPluginRpc(proxy.RpcProxy):

    BASE_RPC_API_VERSION = '1.0'

    def __init__(self, host):
        super(MeteringPluginRpc,
              self).__init__(topic=topics.METERING_AGENT,
                             default_version=self.BASE_RPC_API_VERSION)

    def _get_sync_data_metering(self, context):
        try:
            return self.call(context,
                             self.make_msg('get_sync_data_metering',
                                           host=self.host),
                             topic=topics.METERING_PLUGIN)
        except Exception:
            LOG.exception(_("Failed synchronizing routers"))


class MeteringAgent(MeteringPluginRpc, manager.Manager):

    Opts = [
        cfg.StrOpt('driver',
                   default='neutron.services.metering.drivers.noop.'
                   'noop_driver.NoopMeteringDriver',
                   help=_("Metering driver")),
        cfg.IntOpt('measure_interval', default=30,
                   help=_("Interval between two metering measures")),
        cfg.IntOpt('report_interval', default=300,
                   help=_("Interval between two metering reports")),
    ]

    def __init__(self, host, conf=None):
        self.conf = conf or cfg.CONF
        self._load_drivers()
        self.root_helper = config.get_root_helper(self.conf)
        self.context = context.get_admin_context_without_session()
        self.metering_info = {}
        self.metering_loop = loopingcall.FixedIntervalLoopingCall(
            self._metering_loop
        )
        measure_interval = self.conf.measure_interval
        self.last_report = 0
        self.metering_loop.start(interval=measure_interval)
        self.host = host

        self.label_tenant_id = {}
        self.routers = {}
        self.metering_infos = {}
        super(MeteringAgent, self).__init__(host=self.conf.host)

    def _load_drivers(self):
        """Loads plugin-driver from configuration."""
        LOG.info(_("Loading Metering driver %s"), self.conf.driver)
        if not self.conf.driver:
            raise SystemExit(_('A metering driver must be specified'))
        self.metering_driver = importutils.import_object(
            self.conf.driver, self, self.conf)

    def _metering_notification(self):
        for label_id, info in self.metering_infos.items():
            data = {'label_id': label_id,
                    'tenant_id': self.label_tenant_id.get(label_id),
                    'pkts': info['pkts'],
                    'bytes': info['bytes'],
                    'time': info['time'],
                    'first_update': info['first_update'],
                    'last_update': info['last_update'],
                    'host': self.host}

            LOG.debug(_("Send metering report: %s"), data)
            notifier_api.notify(self.context,
                                notifier_api.publisher_id('metering'),
                                'l3.meter',
                                notifier_api.CONF.default_notification_level,
                                data)
            info['pkts'] = 0
            info['bytes'] = 0
            info['time'] = 0

    def _purge_metering_info(self):
        ts = int(time.time())
        report_interval = self.conf.report_interval
        for label_id, info in self.metering_info.items():
            if info['last_update'] > ts + report_interval:
                del self.metering_info[label_id]

    def _add_metering_info(self, label_id, pkts, bytes):
        ts = int(time.time())
        info = self.metering_infos.get(label_id, {'bytes': 0,
                                                  'pkts': 0,
                                                  'time': 0,
                                                  'first_update': ts,
                                                  'last_update': ts})
        info['bytes'] += bytes
        info['pkts'] += pkts
        info['time'] += ts - info['last_update']
        info['last_update'] = ts

        self.metering_infos[label_id] = info

        return info

    def _add_metering_infos(self):
        self.label_tenant_id = {}
        for router in self.routers.values():
            tenant_id = router['tenant_id']
            labels = router.get(constants.METERING_LABEL_KEY, [])
            for label in labels:
                label_id = label['id']
                self.label_tenant_id[label_id] = tenant_id

            tenant_id = self.label_tenant_id.get
        accs = self._get_traffic_counters(self.context, self.routers.values())
        if not accs:
            return

        for label_id, acc in accs.items():
            self._add_metering_info(label_id, acc['pkts'], acc['bytes'])

    def _metering_loop(self):
        self._add_metering_infos()

        ts = int(time.time())
        delta = ts - self.last_report

        report_interval = self.conf.report_interval
        if delta > report_interval:
            self._metering_notification()
            self._purge_metering_info()
            self.last_report = ts

    @utils.synchronized('metering-agent')
    def _invoke_driver(self, context, meterings, func_name):
        try:
            return getattr(self.metering_driver, func_name)(context, meterings)
        except AttributeError:
            LOG.exception(_("Driver %(driver)s does not implement %(func)s"),
                          {'driver': self.conf.driver,
                           'func': func_name})
        except RuntimeError:
            LOG.exception(_("Driver %(driver)s:%(func)s runtime error"),
                          {'driver': self.conf.driver,
                           'func': func_name})

    @periodic_task.periodic_task(run_immediately=True)
    def _sync_routers_task(self, context):
        routers = self._get_sync_data_metering(self.context)
        if not routers:
            return
        self._update_routers(context, routers)

    def router_deleted(self, context, router_id):
        self._add_metering_infos()

        if router_id in self.routers:
            del self.routers[router_id]

        return self._invoke_driver(context, router_id,
                                   'remove_router')

    def routers_updated(self, context, routers=None):
        if not routers:
            routers = self._get_sync_data_metering(self.context)
        if not routers:
            return
        self._update_routers(context, routers)

    def _update_routers(self, context, routers):
        for router in routers:
            self.routers[router['id']] = router

        return self._invoke_driver(context, routers,
                                   'update_routers')

    def _get_traffic_counters(self, context, routers):
        LOG.debug(_("Get router traffic counters"))
        return self._invoke_driver(context, routers, 'get_traffic_counters')

    def update_metering_label_rules(self, context, routers):
        LOG.debug(_("Update metering rules from agent"))
        return self._invoke_driver(context, routers,
                                   'update_metering_label_rules')

    def add_metering_label(self, context, routers):
        LOG.debug(_("Creating a metering label from agent"))
        return self._invoke_driver(context, routers,
                                   'add_metering_label')

    def remove_metering_label(self, context, routers):
        self._add_metering_infos()

        LOG.debug(_("Delete a metering label from agent"))
        return self._invoke_driver(context, routers,
                                   'remove_metering_label')


class MeteringAgentWithStateReport(MeteringAgent):

    def __init__(self, host, conf=None):
        super(MeteringAgentWithStateReport, self).__init__(host=host,
                                                           conf=conf)
        self.state_rpc = agent_rpc.PluginReportStateAPI(topics.PLUGIN)
        self.agent_state = {
            'binary': 'neutron-metering-agent',
            'host': host,
            'topic': topics.METERING_AGENT,
            'configurations': {
                'metering_driver': self.conf.driver,
                'measure_interval':
                self.conf.measure_interval,
                'report_interval': self.conf.report_interval
            },
            'start_flag': True,
            'agent_type': constants.AGENT_TYPE_METERING}
        report_interval = cfg.CONF.AGENT.report_interval
        self.use_call = True
        if report_interval:
            self.heartbeat = loopingcall.FixedIntervalLoopingCall(
                self._report_state)
            self.heartbeat.start(interval=report_interval)

    def _report_state(self):
        try:
            self.state_rpc.report_state(self.context, self.agent_state,
                                        self.use_call)
            self.agent_state.pop('start_flag', None)
            self.use_call = False
        except AttributeError:
            # This means the server does not support report_state
            LOG.warn(_("Neutron server does not support state report."
                       " State report for this agent will be disabled."))
            self.heartbeat.stop()
            return
        except Exception:
            LOG.exception(_("Failed reporting state!"))

    def agent_updated(self, context, payload):
        LOG.info(_("agent_updated by server side %s!"), payload)


def main():
    eventlet.monkey_patch()
    conf = cfg.CONF
    conf.register_opts(MeteringAgent.Opts)
    config.register_agent_state_opts_helper(conf)
    config.register_root_helper(conf)
    conf(project='neutron')
    config.setup_logging(conf)
    server = neutron_service.Service.create(
        binary='neutron-metering-agent',
        topic=topics.METERING_AGENT,
        report_interval=cfg.CONF.AGENT.report_interval,
        manager='neutron.services.metering.agents.'
                'metering_agent.MeteringAgentWithStateReport')
    service.launch(server).wait()
