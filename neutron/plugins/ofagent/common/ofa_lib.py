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

from ryu.app.ofctl import api as ryu_api
from ryu.lib import dpid as dpid_lib
from ryu.lib.packet import arp
from ryu.lib.packet import ethernet
from ryu.lib.packet import packet
from ryu.lib.packet import vlan
from ryu.ofproto import ether as ether

from neutron.openstack.common import log as logging
from neutron.plugins.openvswitch.common import constants


LOG = logging.getLogger(__name__)


class OFANeutronAgentLib(object):

    def __init__(self, ryuapp):
        self.ryuapp = ryuapp
        """self._arp_tbl: map an ip and a mac in a netwok.
            {newtork1: {ip_addr: mac, ...},
             newtork2: {ip_addr: mac, ...},
             ...,
            }
        """
        self._arp_tbl = {}

    def _send_arp_reply(self, datapath, port, pkt):
        LOG.debug(_("packet-out %s"), pkt)
        ofp = datapath.ofproto
        ofpp = datapath.ofproto_parser
        pkt.serialize()
        data = pkt.data
        actions = [ofpp.OFPActionOutput(port=port)]
        out = ofpp.OFPPacketOut(datapath=datapath,
                                buffer_id=ofp.OFP_NO_BUFFER,
                                in_port=ofp.OFPP_CONTROLLER,
                                actions=actions,
                                data=data)
        ryu_api.send_msg(self.ryuapp, out)

    def _add_flow_to_avoid_unknown_packet(self, datapath, match):
        LOG.debug(_("add flow to avoid an unknown packet from packet-in"))
        ofp = datapath.ofproto
        ofpp = datapath.ofproto_parser
        instructions = [ofpp.OFPInstructionGotoTable(
            table_id=constants.FLOOD_TO_TUN)]
        out = ofpp.OFPFlowMod(datapath,
                              table_id=constants.PATCH_LV_TO_TUN,
                              command=ofp.OFPFC_ADD,
                              idle_timeout=5,
                              priority=20,
                              match=match,
                              instructions=instructions)
        ryu_api.send_msg(self.ryuapp, out)

    def _send_unknown_packet(self, msg, in_port, out_port):
        LOG.debug(_("unknown packet-out in-port %(in_port)s "
                    "out-port %(out_port)s msg %(msg)s"),
                  {'in_port': in_port, 'out_port': out_port, 'msg': msg})
        datapath = msg.datapath
        ofp = datapath.ofproto
        ofpp = datapath.ofproto_parser
        data = None
        if msg.buffer_id == ofp.OFP_NO_BUFFER:
            data = msg.data
        actions = [ofpp.OFPActionOutput(port=out_port)]
        out = ofpp.OFPPacketOut(datapath=datapath,
                                buffer_id=msg.buffer_id,
                                in_port=in_port,
                                actions=actions,
                                data=data)
        ryu_api.send_msg(self.ryuapp, out)

    def _respond_arp(self, datapath, port, arptbl,
                     pkt_ethernet, pkt_vlan, pkt_arp):
        if pkt_arp.opcode != arp.ARP_REQUEST:
            LOG.debug(_("unknown arp op %s"), pkt_arp.opcode)
            return False
        ip_addr = pkt_arp.dst_ip
        hw_addr = arptbl.get(ip_addr)
        if hw_addr is None:
            LOG.debug(_("unknown arp request %s"), ip_addr)
            return False
        LOG.debug(_("responding arp request %(ip_addr)s -> %(hw_addr)s"),
                  {'ip_addr': ip_addr, 'hw_addr': hw_addr})
        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(ethertype=pkt_ethernet.ethertype,
                                           dst=pkt_ethernet.src,
                                           src=hw_addr))
        pkt.add_protocol(vlan.vlan(cfi=pkt_vlan.cfi,
                                   ethertype=pkt_vlan.ethertype,
                                   pcp=pkt_vlan.pcp,
                                   vid=pkt_vlan.vid))
        pkt.add_protocol(arp.arp(opcode=arp.ARP_REPLY,
                                 src_mac=hw_addr,
                                 src_ip=ip_addr,
                                 dst_mac=pkt_arp.src_mac,
                                 dst_ip=pkt_arp.src_ip))
        self._send_arp_reply(datapath, port, pkt)
        return True

    def add_arp_table_entry(self, network, ip, mac):
        LOG.debug(_("added arp table entry: "
                    "network %(network)s ip %(ip)s mac %(mac)s"),
                  {'network': network, 'ip': ip, 'mac': mac})
        if network in self._arp_tbl:
            self._arp_tbl[network][ip] = mac
        else:
            self._arp_tbl[network] = {ip: mac}

    def del_arp_table_entry(self, network, ip):
        LOG.debug(_("deleted arp table entry: network %(network)s ip %(ip)s"),
                  {'network': network, 'ip': ip})
        del self._arp_tbl[network][ip]
        if self._arp_tbl[network] == {}:
            del self._arp_tbl[network]

    def packet_in_handler(self, ev):
        """Check a packet-in message.

           Build and output an arp reply if a packet-in message is
           an arp packet.
        """
        msg = ev.msg
        LOG.debug(_("packet-in msg %s"), msg)
        datapath = msg.datapath
        ofp = datapath.ofproto
        ofpp = datapath.ofproto_parser
        port = msg.match['in_port']
        pkt = packet.Packet(msg.data)
        LOG.info(_("packet-in dpid %(dpid)s in_port %(port)s pkt %(pkt)s"),
                 {'dpid': dpid_lib.dpid_to_str(datapath.id),
                 'port': port, 'pkt': pkt})
        pkt_ethernet = None
        pkt_vlan = None
        pkt_arp = None
        pkt_ethernet = pkt.get_protocol(ethernet.ethernet)
        if not pkt_ethernet:
            LOG.info(_("non-ethernet packet"))
        else:
            pkt_vlan = pkt.get_protocol(vlan.vlan)
            if not pkt_vlan:
                LOG.info(_("non-vlan packet"))
        if pkt_vlan:
            network = pkt_vlan.vid
            pkt_arp = pkt.get_protocol(arp.arp)
            if not pkt_arp:
                LOG.info(_("non-arp packet"))
                # add a flow to skip a packet-in to a controller
                match = ofpp.OFPMatch(eth_type=ether.ETH_TYPE_8021Q,
                                      vlan_vid=network | ofp.OFPVID_PRESENT)
                self._add_flow_to_avoid_unknown_packet(datapath, match)
                # send a non-arp packet to the table.
                self._send_unknown_packet(msg, port, ofp.OFPP_TABLE)
                return
        else:
            # flood an unknown packet.
            self._send_unknown_packet(msg, port, ofp.OFPP_FLOOD)
            return

        arptbl = self._arp_tbl.get(network)
        if arptbl:
            if self._respond_arp(datapath, port, arptbl,
                                 pkt_ethernet, pkt_vlan, pkt_arp):
                return
        else:
            LOG.info(_("unknown network %s"), network)
        # add a flow to skip a packet-in to a controller
        match = ofpp.OFPMatch(eth_type=ether.ETH_TYPE_ARP,
                              vlan_vid=network | ofp.OFPVID_PRESENT,
                              arp_op=arp.ARP_REQUEST,
                              arp_tpa=pkt_arp.dst_ip)
        self._add_flow_to_avoid_unknown_packet(datapath, match)
        # send an unknown arp packet to the table.
        self._send_unknown_packet(msg, port, ofp.OFPP_TABLE)
