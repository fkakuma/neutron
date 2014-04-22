# Copyright (C) 2014 VA Linux Systems Japan K.K.
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
import sys

import mock

from neutron.openstack.common import importutils
from neutron.tests import base
from neutron.tests.unit.ofagent import fake_oflib


_OFALIB_NAME = 'neutron.plugins.ofagent.common.ofa_lib'


class OFAAgentTestCase(base.BaseTestCase):

    @classmethod
    def setUpClass(cls):
        cls.fake_oflib_of = fake_oflib.patch_fake_oflib_of().start()
        cls.network1 = 10
        cls.net1_ip1 = '10.1.2.20'
        cls.net1_mac1 = '11:11:11:44:55:66'
        cls.net1_ip2 = '10.1.2.21'
        cls.net1_mac2 = '11:11:11:44:55:67'
        cls.network2 = 20
        cls.net2_ip1 = '10.2.2.20'
        cls.net2_mac1 = '22:22:22:44:55:66'

        cls.packet_mod = mock.Mock()
        cls.proto_ethernet_mod = mock.Mock()
        cls.proto_vlan_mod = mock.Mock()
        cls.proto_vlan_mod.vid = cls.network1
        cls.proto_arp_mod = mock.Mock()
        cls.fake_get_protocol = mock.Mock(return_value=cls.proto_vlan_mod)
        cls.packet_mod.get_protocol = cls.fake_get_protocol
        cls.fake_add_protocol = mock.Mock(return_value=cls.proto_vlan_mod)
        cls.packet_mod.add_protocol = cls.fake_add_protocol
        cls.arp = sys.modules['ryu.lib.packet.arp']
        cls.arp_arp = mock.Mock()
        cls.arp.arp = mock.Mock(return_value=cls.arp_arp)
        cls.ethernet = sys.modules['ryu.lib.packet.ethernet']
        cls.ethernet_ethernet = mock.Mock()
        cls.ethernet.ethernet = mock.Mock(return_value=cls.ethernet_ethernet)
        cls.vlan = sys.modules['ryu.lib.packet.vlan']
        cls.vlan_vlan = mock.Mock()
        cls.vlan.vlan = mock.Mock(return_value=cls.vlan_vlan)
        cls.Packet = sys.modules['ryu.lib.packet.packet.Packet']
        cls.Packet.return_value = cls.packet_mod

    def setUp(self):
        super(OFAAgentTestCase, self).setUp()
        self.ryuapp = mock.Mock()
        self.inport = '1'
        self.ev = mock.Mock()
        self.datapath = mock.Mock()
        self.ofproto = mock.Mock()
        self.datapath.ofproto = self.ofproto
        self.ofproto.OFPVID_PRESENT = 0x1000
        self.ofproto.OFPP_TABLE = 0xfffffff9
        self.ofproto.OFP_NO_BUFFER = 0xffffffff
        self.ofparser = mock.Mock()
        self.datapath.ofproto_parser = self.ofparser
        self.OFPActionOutput = mock.Mock()
        self.OFPActionOutput.return_value = mock.Mock()
        self.ofparser.OFPActionOutput = self.OFPActionOutput
        self.msg = mock.Mock()
        self.msg.datapath = self.datapath
        self.msg.buffer_id = self.ofproto.OFP_NO_BUFFER
        self.msg_data = 'test_message_data'
        self.msg.data = self.msg_data
        self.ev.msg = self.msg
        self.msg.match = {'in_port': self.inport}

    def tearDown(self):
        super(OFAAgentTestCase, self).tearDown()
        self.fake_get_protocol.reset_mock()
        self.fake_add_protocol.reset_mock()


class TestOFANeutronAgentLib(OFAAgentTestCase):

    def setUp(self):
        super(TestOFANeutronAgentLib, self).setUp()

        self.mod_lib = importutils.import_module(_OFALIB_NAME)
        self.ofalib = self.mod_lib.OFANeutronAgentLib(self.ryuapp)
        self.packet_mod.get_protocol = self._fake_get_protocol
        self._fake_get_protocol_ethernet = True
        self._fake_get_protocol_vlan = True
        self._fake_get_protocol_arp = True

    def test__send_unknown_packet_no_buffer(self):
        in_port = 3
        out_port = self.ofproto.OFPP_TABLE
        self.msg.buffer_id = self.ofproto.OFP_NO_BUFFER
        self.ofalib._send_unknown_packet(self.msg, in_port, out_port)
        actions = [self.OFPActionOutput.return_value]
        self.ofparser.OFPPacketOut.assert_called_once_with(
            datapath=self.datapath,
            buffer_id=self.msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=self.msg_data)

    def test__send_unknown_packet_existence_buffer(self):
        in_port = 3
        out_port = self.ofproto.OFPP_TABLE
        self.msg.buffer_id = 256
        self.ofalib._send_unknown_packet(self.msg, in_port, out_port)
        actions = [self.OFPActionOutput.return_value]
        self.ofparser.OFPPacketOut.assert_called_once_with(
            datapath=self.datapath,
            buffer_id=self.msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=None)

    def test__respond_arp(self):
        self.ofalib._arp_tbl = {self.network1: {self.net1_ip1: self.net1_mac1}}
        port = 3
        arptbl = self.ofalib._arp_tbl[self.network1]
        pkt_ethernet = mock.Mock()
        pkt_vlan = mock.Mock()
        pkt_arp = mock.Mock()
        pkt_arp.opcode = self.arp.ARP_REQUEST
        pkt_arp.dst_ip = self.net1_ip1
        with mock.patch.object(
            self.ofalib, '_send_arp_reply'
        ) as send_arp_rep_fn:
            self.assertTrue(
                self.ofalib._respond_arp(self.datapath, port, arptbl,
                                         pkt_ethernet, pkt_vlan, pkt_arp))
        self.assertEqual(self.fake_add_protocol.call_args_list,
                         [mock.call(self.ethernet_ethernet),
                          mock.call(self.vlan_vlan),
                          mock.call(self.arp_arp)])
        send_arp_rep_fn.assert_called_once_with(
            self.datapath, port, self.packet_mod)

    def test__respond_arp_non_arp_req(self):
        self.ofalib._arp_tbl = {self.network1: {self.net1_ip1: self.net1_mac1}}
        port = 3
        arptbl = self.ofalib._arp_tbl[self.network1]
        pkt_ethernet = mock.Mock()
        pkt_vlan = mock.Mock()
        pkt_arp = mock.Mock()
        pkt_arp.opcode = self.arp.ARP_REPLY
        self.assertFalse(
            self.ofalib._respond_arp(self.datapath, port, arptbl,
                                     pkt_ethernet, pkt_vlan, pkt_arp))

    def test__respond_arp_ip_not_found_in_arptable(self):
        self.ofalib._arp_tbl = {self.network1: {self.net1_ip1: self.net1_mac1}}
        port = 3
        arptbl = self.ofalib._arp_tbl[self.network1]
        pkt_ethernet = mock.Mock()
        pkt_vlan = mock.Mock()
        pkt_arp = mock.Mock()
        pkt_arp.opcode = self.arp.ARP_REQUEST
        pkt_arp.dst_ip = self.net1_ip2
        self.assertFalse(
            self.ofalib._respond_arp(self.datapath, port, arptbl,
                                     pkt_ethernet, pkt_vlan, pkt_arp))

    def test_add_arp_table_entry(self):
        self.ofalib.add_arp_table_entry(self.network1,
                                        self.net1_ip1, self.net1_mac1)
        self.assertEqual(self.ofalib._arp_tbl,
                         {self.network1: {self.net1_ip1: self.net1_mac1}})

    def test_add_arp_table_entry_multiple_net(self):
        self.ofalib.add_arp_table_entry(self.network1,
                                        self.net1_ip1, self.net1_mac1)
        self.ofalib.add_arp_table_entry(self.network2,
                                        self.net2_ip1, self.net2_mac1)
        self.assertEqual(self.ofalib._arp_tbl,
                         {self.network1: {self.net1_ip1: self.net1_mac1},
                          self.network2: {self.net2_ip1: self.net2_mac1}})

    def test_add_arp_table_entry_multiple_ip(self):
        self.ofalib.add_arp_table_entry(self.network1,
                                        self.net1_ip1, self.net1_mac1)
        self.ofalib.add_arp_table_entry(self.network1,
                                        self.net1_ip2, self.net1_mac2)
        self.assertEqual(self.ofalib._arp_tbl,
                         {self.network1: {self.net1_ip1: self.net1_mac1,
                                          self.net1_ip2: self.net1_mac2}})

    def test_del_arp_table_entry(self):
        self.ofalib._arp_tbl = {self.network1: {self.net1_ip1: self.net1_mac1}}
        self.ofalib.del_arp_table_entry(self.network1, self.net1_ip1)
        self.assertEqual(self.ofalib._arp_tbl, {})

    def test_del_arp_table_entry_multiple_net(self):
        self.ofalib._arp_tbl = {self.network1: {self.net1_ip1: self.net1_mac1},
                                self.network2: {self.net2_ip1: self.net2_mac1}}
        self.ofalib.del_arp_table_entry(self.network1, self.net1_ip1)
        self.assertEqual(self.ofalib._arp_tbl,
                         {self.network2: {self.net2_ip1: self.net2_mac1}})

    def test_del_arp_table_entry_multiple_ip(self):
        self.ofalib._arp_tbl = {self.network1: {self.net1_ip1: self.net1_mac1,
                                                self.net1_ip2: self.net1_mac2}}
        self.ofalib.del_arp_table_entry(self.network1, self.net1_ip2)
        self.assertEqual(self.ofalib._arp_tbl,
                         {self.network1: {self.net1_ip1: self.net1_mac1}})

    def _fake_get_protocol(self, net_type):
        if net_type == self.ethernet.ethernet:
            if self._fake_get_protocol_ethernet:
                return self.proto_ethernet_mod
            else:
                return None
        if net_type == self.vlan.vlan:
            if self._fake_get_protocol_vlan:
                return self.proto_vlan_mod
            else:
                return None
        if net_type == self.arp.arp:
            if self._fake_get_protocol_arp:
                return self.proto_arp_mod
            else:
                return None

    def test_packet_in_handler(self):
        self.ofalib._arp_tbl = {self.network1: {self.net1_ip1: self.net1_mac1}}
        with contextlib.nested(
            mock.patch.object(self.ofalib, '_respond_arp',
                              return_value=True),
            mock.patch.object(self.ofalib,
                              '_add_flow_to_avoid_unknown_packet'),
            mock.patch.object(self.ofalib,
                              '_send_unknown_packet'),
        ) as (res_arp_fn, add_flow_fn, send_unknown_pk_fn):
            self.ofalib.packet_in_handler(self.ev)
        self.assertEqual(add_flow_fn.call_count, 0)
        self.assertEqual(send_unknown_pk_fn.call_count, 0)
        res_arp_fn.assert_called_once_with(
            self.datapath, self.inport,
            self.ofalib._arp_tbl[self.network1],
            self.proto_ethernet_mod, self.proto_vlan_mod, self.proto_arp_mod)

    def test_packet_in_handler_non_ethernet(self):
        self.ofalib._arp_tbl = {self.network1: {self.net1_ip1: self.net1_mac1}}
        self._fake_get_protocol_ethernet = False
        with contextlib.nested(
            mock.patch.object(self.ofalib, '_respond_arp',
                              return_value=True),
            mock.patch.object(self.ofalib,
                              '_add_flow_to_avoid_unknown_packet'),
            mock.patch.object(self.ofalib,
                              '_send_unknown_packet'),
        ) as (res_arp_fn, add_flow_fn, send_unknown_pk_fn):
            self.ofalib.packet_in_handler(self.ev)
        self.assertEqual(add_flow_fn.call_count, 0)
        self.assertEqual(send_unknown_pk_fn.call_count, 1)
        self.assertEqual(res_arp_fn.call_count, 0)

    def test_packet_in_handler_non_vlan(self):
        self.ofalib._arp_tbl = {self.network1: {self.net1_ip1: self.net1_mac1}}
        self._fake_get_protocol_vlan = False
        with contextlib.nested(
            mock.patch.object(self.ofalib, '_respond_arp',
                              return_value=True),
            mock.patch.object(self.ofalib,
                              '_add_flow_to_avoid_unknown_packet'),
            mock.patch.object(self.ofalib,
                              '_send_unknown_packet'),
        ) as (res_arp_fn, add_flow_fn, send_unknown_pk_fn):
            self.ofalib.packet_in_handler(self.ev)
        self.assertEqual(add_flow_fn.call_count, 0)
        self.assertEqual(send_unknown_pk_fn.call_count, 1)
        self.assertEqual(res_arp_fn.call_count, 0)

    def test_packet_in_handler_non_arp(self):
        self.ofalib._arp_tbl = {self.network1: {self.net1_ip1: self.net1_mac1}}
        self._fake_get_protocol_arp = False
        with contextlib.nested(
            mock.patch.object(self.ofalib, '_respond_arp',
                              return_value=True),
            mock.patch.object(self.ofalib,
                              '_add_flow_to_avoid_unknown_packet'),
            mock.patch.object(self.ofalib,
                              '_send_unknown_packet'),
        ) as (res_arp_fn, add_flow_fn, send_unknown_pk_fn):
            self.ofalib.packet_in_handler(self.ev)
        self.assertEqual(add_flow_fn.call_count, 1)
        self.assertEqual(send_unknown_pk_fn.call_count, 1)
        self.assertEqual(res_arp_fn.call_count, 0)

    def test_packet_in_handler_unknown_network(self):
        self.ofalib._arp_tbl = {self.network1: {self.net1_ip1: self.net1_mac1}}
        with contextlib.nested(
            mock.patch.object(self.ofalib, '_respond_arp',
                              return_value=False),
            mock.patch.object(self.ofalib,
                              '_add_flow_to_avoid_unknown_packet'),
            mock.patch.object(self.ofalib,
                              '_send_unknown_packet'),
        ) as (res_arp_fn, add_flow_fn, send_unknown_pk_fn):
            self.ofalib.packet_in_handler(self.ev)
        self.assertEqual(add_flow_fn.call_count, 1)
        self.assertEqual(send_unknown_pk_fn.call_count, 1)
        res_arp_fn.assert_called_once_with(
            self.datapath, self.inport,
            self.ofalib._arp_tbl[self.network1],
            self.proto_ethernet_mod, self.proto_vlan_mod, self.proto_arp_mod)
