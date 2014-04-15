# Copyright (C) 2014 VA Linux Systems Japan K.K.
# Based on test for openvswitch agent(test_ovs_neutron_agent.py).
#
# Copyright (c) 2012 OpenStack Foundation.
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
# @author: Fumihiko Kakuma, VA Linux Systems Japan K.K.

import contextlib

import mock

from neutron.agent import l2population_rpc
from neutron.common import constants as n_const
from neutron.plugins.openvswitch.agent import ovs_neutron_agent
from neutron.tests import base


class FakeNeutronAgent(l2population_rpc.L2populationRpcCallBackTunnelMixin):

    def fdb_add(self, context, fdb_entries):
        pass

    def fdb_remove(self, context, fdb_entries):
        pass

    def add_fdb_flow(self, context, fdb_entries):
        pass

    def del_fdb_flow(self, context, fdb_entries):
        pass

    def setup_tunnel_port(self, agent_ip, network_type):
        pass

    def cleanup_tunnel_port(self, tun_ofport, tunnel_type):
        pass


class TestL2populationRpcCallBackTunnelMixin(base.BaseTestCase):

    def setUp(self):
        super(TestL2populationRpcCallBackTunnelMixin, self).setUp()
        self.fakeagent = FakeNeutronAgent()

        self.local_ip = '127.0.0.1'
        self.agent_ip1 = '10.1.0.1'
        self.agent_ip2 = '10.2.0.1'
        self.agent_ip3 = '10.3.0.1'
        self.ofport1 = 'ofport1'
        self.ofport2 = 'ofport2'
        self.ofport3 = 'ofport3'
        self.type_gre = 'gre'
        self.ofports = {
            self.type_gre: {
                self.agent_ip1: self.ofport1,
                self.agent_ip2: self.ofport2,
                self.agent_ip3: self.ofport3,
            }
        }

        self.net1 = 'net1'
        self.vlan1 = 1
        self.phys1 = 'phys1'
        self.segid1 = 'tun1'
        self.mac1 = 'mac1'
        self.ip1 = '1.1.1.1'
        self.vif1 = 'vifid1'
        self.port1 = 'port1'
        self.agent_ports1 = {
            self.local_ip: [],
            self.agent_ip1: [[self.mac1, self.ip1]]
        }

        self.net2 = 'net2'
        self.vlan2 = 2
        self.phys2 = 'phys2'
        self.segid2 = 'tun2'
        self.mac2 = 'mac2'
        self.ip2 = '2.2.2.2'
        self.vif2 = 'vifid2'
        self.port2 = 'port2'
        self.agent_ports2 = {
            self.local_ip: [],
            self.agent_ip2: [[self.mac2, self.ip2]]
        }

        self.net3 = 'net3'
        self.vlan3 = 3
        self.phys3 = 'phys3'
        self.segid3 = 'tun3'
        self.mac3 = 'mac3'
        self.ip3 = '3.3.3.3'
        self.vif3 = 'vifid3'
        self.port3 = 'port3'
        self.agent_ports3 = {
            self.local_ip: [],
            self.agent_ip3: [[self.mac3, self.ip3]]
        }

        self.agent_ports = {
            self.agent_ip1: [[self.mac1, self.ip1]],
            self.agent_ip2: [[self.mac2, self.ip2]],
            self.agent_ip3: [[self.mac3, self.ip3]],
        }

        self.fdb_entries1 = {
            self.net1: {
                'network_type': self.type_gre,
                'segment_id': self.segid1,
                'ports': self.agent_ports1,
            },
            self.net2: {
                'network_type': self.type_gre,
                'segment_id': self.segid2,
                'ports': self.agent_ports2,
            },
            self.net3: {
                'network_type': self.type_gre,
                'segment_id': self.segid3,
                'ports': self.agent_ports3,
            },
        }

        self.vif_ports1 = {self.vif1: self.port1}
        self.vif_ports2 = {self.vif2: self.port2}
        self.vif_ports3 = {self.vif3: self.port3}
        self.lvm1 = ovs_neutron_agent.LocalVLANMapping(
            self.vlan1, self.type_gre, self.phys1, self.segid1,
            self.vif_ports1)
        self.lvm2 = ovs_neutron_agent.LocalVLANMapping(
            self.vlan2, self.type_gre, self.phys2, self.segid2,
            self.vif_ports2)
        self.lvm3 = ovs_neutron_agent.LocalVLANMapping(
            self.vlan3, self.type_gre, self.phys3, self.segid3,
            self.vif_ports3)

        self.local_vlan_map1 = {
            self.net1: self.lvm1,
            self.net2: self.lvm2,
            self.net3: self.lvm3,
        }

        self.upd_fdb_entry1_val = {
            self.net1: {
                self.agent_ip1: {
                    'before': [[self.mac1, self.ip1]],
                    'after': [[self.mac2, self.ip2]],
                },
                self.agent_ip2: {
                    'before': [[self.mac1, self.ip1]],
                    'after': [[self.mac2, self.ip2]],
                },
            },
            self.net2: {
                self.agent_ip3: {
                    'before': [[self.mac1, self.ip1]],
                    'after': [[self.mac3, self.ip3]],
                },
            },
        }
        self.upd_fdb_entry1 = {'chg_ip': self.upd_fdb_entry1_val}

    def test_get_agent_ports_no_data(self):
        for lvm, agent_ports in self.fakeagent.get_agent_ports(
            self.fdb_entries1, {}):
            self.assertIsNone(lvm)
            self.assertEqual({}, agent_ports)

    def test_get_agent_ports_non_existence_key_in_lvm(self):
        results = {}
        del self.local_vlan_map1[self.net2]
        for lvm, agent_ports in self.fakeagent.get_agent_ports(
            self.fdb_entries1, self.local_vlan_map1):
            results[lvm] = agent_ports
        expected = {
            self.lvm1: {self.agent_ip1: [[self.mac1, self.ip1]],
                        self.local_ip: []},
            None: {},
            self.lvm3: {self.agent_ip3: [[self.mac3, self.ip3]],
                        self.local_ip: []},
        }
        self.assertEqual(expected, results)

    def test_get_agent_ports_no_agent_ports(self):
        results = {}
        self.fdb_entries1[self.net2]['ports'] = {}
        for lvm, agent_ports in self.fakeagent.get_agent_ports(
            self.fdb_entries1, self.local_vlan_map1):
            results[lvm] = agent_ports
        expected = {
            self.lvm1: {self.agent_ip1: [[self.mac1, self.ip1]],
                        self.local_ip: []},
            self.lvm2: {},
            self.lvm3: {self.agent_ip3: [[self.mac3, self.ip3]],
                        self.local_ip: []},
        }
        self.assertEqual(expected, results)

    def test_fdb_add_tun(self):
        with contextlib.nested(
            mock.patch.object(self.fakeagent, 'setup_tunnel_port'),
            mock.patch.object(self.fakeagent, 'add_fdb_flow'),
        ) as (mock_setup_tunnel_port, mock_add_fdb_flow):
            self.fakeagent.fdb_add_tun('context', self.lvm1,
                                       self.agent_ports, self.ofports)
        expected = [
            mock.call([self.mac1, self.ip1], self.lvm1, self.ofport1),
            mock.call([self.mac2, self.ip2], self.lvm1, self.ofport2),
            mock.call([self.mac3, self.ip3], self.lvm1, self.ofport3),
        ]
        self.assertEqual(sorted(expected),
                         sorted(mock_add_fdb_flow.call_args_list))

    def test_fdb_add_tun_non_existence_key_in_ofports(self):
        ofport = self.lvm1.network_type + '0a0a0a0a'
        del self.ofports[self.type_gre][self.agent_ip2]
        with contextlib.nested(
            mock.patch.object(self.fakeagent, 'setup_tunnel_port',
                              return_value=ofport),
            mock.patch.object(self.fakeagent, 'add_fdb_flow'),
        ) as (mock_setup_tunnel_port, mock_add_fdb_flow):
            self.fakeagent.fdb_add_tun('context', self.lvm1,
                                       self.agent_ports, self.ofports)
        mock_setup_tunnel_port.assert_called_once_with(
            self.agent_ip2, self.lvm1.network_type)
        expected = [
            mock.call([self.mac1, self.ip1], self.lvm1, self.ofport1),
            mock.call([self.mac2, self.ip2], self.lvm1, ofport),
            mock.call([self.mac3, self.ip3], self.lvm1, self.ofport3),
        ]
        self.assertEqual(sorted(expected),
                         sorted(mock_add_fdb_flow.call_args_list))

    def test_fdb_add_tun_unavailable_ofport(self):
        del self.ofports[self.type_gre][self.agent_ip2]
        with contextlib.nested(
            mock.patch.object(self.fakeagent, 'setup_tunnel_port',
                              return_value=0),
            mock.patch.object(self.fakeagent, 'add_fdb_flow'),
        ) as (mock_setup_tunnel_port, mock_add_fdb_flow):
            self.fakeagent.fdb_add_tun('context', self.lvm1,
                                       self.agent_ports, self.ofports)
        mock_setup_tunnel_port.assert_called_once_with(
            self.agent_ip2, self.lvm1.network_type)
        expected = [
            mock.call([self.mac1, self.ip1], self.lvm1, self.ofport1),
            mock.call([self.mac3, self.ip3], self.lvm1, self.ofport3),
        ]
        self.assertEqual(sorted(expected),
                         sorted(mock_add_fdb_flow.call_args_list))

    def test_fdb_remove_tun(self):
        with mock.patch.object(
            self.fakeagent, 'del_fdb_flow') as mock_del_fdb_flow:
            self.fakeagent.fdb_remove_tun('context', self.lvm1,
                                          self.agent_ports, self.ofports)
        expected = [
            mock.call([self.mac1, self.ip1], self.lvm1, self.ofport1),
            mock.call([self.mac2, self.ip2], self.lvm1, self.ofport2),
            mock.call([self.mac3, self.ip3], self.lvm1, self.ofport3),
        ]
        self.assertEqual(sorted(expected),
                         sorted(mock_del_fdb_flow.call_args_list))

    def test_fdb_remove_tun_flooding_entry(self):
        self.agent_ports[self.agent_ip2] = [n_const.FLOODING_ENTRY]
        with contextlib.nested(
            mock.patch.object(self.fakeagent, 'del_fdb_flow'),
            mock.patch.object(self.fakeagent, 'cleanup_tunnel_port'),
        ) as (mock_del_fdb_flow, mock_cleanup_tunnel_port):
            self.fakeagent.fdb_remove_tun('context', self.lvm1,
                                          self.agent_ports, self.ofports)
        expected = [
            mock.call([self.mac1, self.ip1], self.lvm1, self.ofport1),
            mock.call([n_const.FLOODING_ENTRY[0], n_const.FLOODING_ENTRY[1]],
                      self.lvm1, self.ofport2),
            mock.call([self.mac3, self.ip3], self.lvm1, self.ofport3),
        ]
        self.assertEqual(sorted(expected),
                         sorted(mock_del_fdb_flow.call_args_list))
        mock_cleanup_tunnel_port.assert_called_once_with(
            self.ofport2, self.lvm1.network_type)

    def test_fdb_remove_tun_non_existence_key_in_ofports(self):
        del self.ofports[self.type_gre][self.agent_ip2]
        with mock.patch.object(
            self.fakeagent, 'del_fdb_flow') as mock_del_fdb_flow:
            self.fakeagent.fdb_remove_tun('context', self.lvm1,
                                          self.agent_ports, self.ofports)
        expected = [
            mock.call([self.mac1, self.ip1], self.lvm1, self.ofport1),
            mock.call([self.mac3, self.ip3], self.lvm1, self.ofport3),
        ]
        self.assertEqual(sorted(expected),
                         sorted(mock_del_fdb_flow.call_args_list))

    def test_fdb_update(self):
        fake__fdb_chg_ip = mock.Mock()
        self.fakeagent._fdb_chg_ip = fake__fdb_chg_ip
        self.fakeagent.fdb_update('context', self.upd_fdb_entry1)
        fake__fdb_chg_ip.assert_called_once_with(
            'context', self.upd_fdb_entry1_val)

    def test_fdb_update_non_existence_method(self):
        self.assertRaises(NotImplementedError,
                          self.fakeagent.fdb_update,
                          'context', self.upd_fdb_entry1)
