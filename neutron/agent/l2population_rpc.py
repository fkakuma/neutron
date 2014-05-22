# Copyright (c) 2013 OpenStack Foundation.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
# @author: Sylvain Afchain, eNovance SAS
# @author: Francois Eleouet, Orange
# @author: Mathieu Rohon, Orange

import abc

from oslo.config import cfg
import six

from neutron.common import log
from neutron.openstack.common import log as logging

LOG = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class L2populationRpcCallBackMixin(object):

    @log.log
    def add_fdb_entries(self, context, fdb_entries, host=None):
        if not host or host == cfg.CONF.host:
            self.fdb_add(context, fdb_entries)

    @log.log
    def remove_fdb_entries(self, context, fdb_entries, host=None):
        if not host or host == cfg.CONF.host:
            self.fdb_remove(context, fdb_entries)

    @log.log
    def update_fdb_entries(self, context, fdb_entries, host=None):
        if not host or host == cfg.CONF.host:
            self.fdb_update(context, fdb_entries)

    @abc.abstractmethod
    def fdb_add(self, context, fdb_entries):
        pass

    @abc.abstractmethod
    def fdb_remove(self, context, fdb_entries):
        pass

    @abc.abstractmethod
    def fdb_update(self, context, fdb_entries):
        pass


class L2populationRpcCallBackOvsMixin(L2populationRpcCallBackMixin):

    @abc.abstractmethod
    def _add_fdb_flow(self, context, fdb_entries):
        pass

    @abc.abstractmethod
    def _del_fdb_flow(self, context, fdb_entries):
        pass

    @abc.abstractmethod
    def setup_tunnel_port(self, port_name, remote_ip, tunnel_type):
        pass

    @abc.abstractmethod
    def get_ip_in_hex(self, ip_address):
        pass

    def fdb_add_ovs(self, context, fdb_entries, local_vlan_map, local_ip,
                    br, ofports, defer=False):
        LOG.debug(_("fdb_add_ovs received"))
        for network_id, values in fdb_entries.items():
            lvm = local_vlan_map.get(network_id)
            if not lvm:
                # Agent doesn't manage any port in this network
                continue
            agent_ports = values.get('ports')
            agent_ports.pop(local_ip, None)
            if len(agent_ports):
                if defer:
                    br.defer_apply_on()
                for agent_ip, ports in agent_ports.items():
                    # Ensure we have a tunnel port with this remote agent
                    ofport = ofports[lvm.network_type].get(agent_ip)
                    if not ofport:
                        remote_ip_hex = self.get_ip_in_hex(agent_ip)
                        if not remote_ip_hex:
                            continue
                        port_name = '%s-%s' % (lvm.network_type, remote_ip_hex)
                        ofport = self.setup_tunnel_port(port_name, agent_ip,
                                                        lvm.network_type)
                        if ofport == 0:
                            continue
                    for port in ports:
                        self._add_fdb_flow(port, lvm, ofport)
                if defer:
                    br.defer_apply_off()

    def fdb_remove_ovs(self, context, fdb_entries, local_vlan_map, local_ip,
                       br, ofports, defer=False):
        LOG.debug(_("fdb_remove_ovs received"))
        for network_id, values in fdb_entries.items():
            lvm = local_vlan_map.get(network_id)
            if not lvm:
                # Agent doesn't manage any more ports in this network
                continue
            agent_ports = values.get('ports')
            agent_ports.pop(local_ip, None)
            if len(agent_ports):
                if defer:
                    br.defer_apply_on()
                for agent_ip, ports in agent_ports.items():
                    ofport = ofports[lvm.network_type].get(agent_ip)
                    if not ofport:
                        continue
                    for port in ports:
                        self._del_fdb_flow(port, lvm, ofport)
                if defer:
                    br.defer_apply_off()

    def fdb_update(self, context, fdb_entries):
        LOG.debug(_("fdb_update received"))
        for action, values in fdb_entries.items():
            method = '_fdb_' + action
            if not hasattr(self, method):
                raise NotImplementedError()

            getattr(self, method)(context, values)
