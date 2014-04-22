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

import mock


def patch_fake_oflib_of():
    ryu_mod = mock.Mock()
    ryu_base_mod = ryu_mod.base
    ryu_ctrl_mod = ryu_mod.controller
    ryu_hand_mod = ryu_ctrl_mod.handler
    ryu_ctrl_ofpevt = ryu_ctrl_mod.ofp_event
    ryu_hand_mod.MAIN_DISPATCHER = 'main'
    ryu_ctrl_hand_setevc = ryu_hand_mod.set_ev_cls
    ryu_lib_mod = ryu_mod.lib
    ryu_lib_dpid = ryu_lib_mod.dpid
    ryu_lib_hub = ryu_lib_mod.hub
    ryu_packet_mod = ryu_lib_mod.packet
    ryu_packet_arp = ryu_packet_mod.arp
    ryu_packet_eth = ryu_packet_mod.ethernet
    ryu_packet_packet = ryu_packet_mod.packet
    ryu_ofproto_mod = ryu_mod.ofproto
    ryu_ofproto_of13 = ryu_ofproto_mod.ofproto_v1_3
    ryu_ofproto_of13.OFPTT_ALL = 0xff
    ryu_ofproto_of13.OFPG_ANY = 0xffffffff
    ryu_ofproto_of13.OFPP_ANY = 0xffffffff
    ryu_ofproto_of13.OFPFC_ADD = 0
    ryu_ofproto_of13.OFPFC_DELETE = 3
    ryu_ofproto_of13.OFPVID_PRESENT = 0x1000
    ryu_app_mod = ryu_mod.app
    ryu_app_ofctl_mod = ryu_app_mod.ofctl
    ryu_ofctl_api = ryu_app_ofctl_mod.api
    return mock.patch.dict(
        'sys.modules',
        {'ryu': ryu_mod,
         'ryu.base': ryu_base_mod,
         'ryu.controller': ryu_ctrl_mod,
         'ryu.controller.handler': ryu_hand_mod,
         'ryu.controller.handler.set_ev_cls': ryu_ctrl_hand_setevc,
         'ryu.controller.ofp_event': ryu_ctrl_ofpevt,
         'ryu.lib': ryu_lib_mod,
         'ryu.lib.dpid': ryu_lib_dpid,
         'ryu.lib.hub': ryu_lib_hub,
         'ryu.lib.packet': ryu_packet_mod,
         'ryu.lib.packet.arp': ryu_packet_arp,
         'ryu.lib.packet.ethernet': ryu_packet_eth,
         'ryu.lib.packet.packet': ryu_packet_packet,
         'ryu.ofproto': ryu_ofproto_mod,
         'ryu.ofproto.ofproto_v1_3': ryu_ofproto_of13,
         'ryu.app': ryu_app_mod,
         'ryu.app.ofctl': ryu_app_ofctl_mod,
         'ryu.app.ofctl.api': ryu_ofctl_api})
