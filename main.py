from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
import networkx as nx
import random
from ryu.lib.packet import ethernet, packet, ether_types
from ryu.topology.api import get_all_host, get_all_link, get_all_switch, get_host

class SDNController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SDNController, self).__init__(*args, **kwargs)
        self.network_graph = None
        self.path = None

    def set_random_link_costs(self):
        for link in self.network_graph['links']:
            link['cost'] = random.randint(1, 10)

    def get_best_path(self, src, dst):
        graph = nx.Graph(self.network_graph['links'])
        return nx.shortest_path(graph, src, dst)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.get_topology_data()
        self.add_flow(datapath, 0, match, actions)
    

    def add_flow(self, datapath, priority, match, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        instructions = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        flow_mod = parser.OFPFlowMod(datapath=datapath, priority=priority, match=match, instructions=instructions)
        datapath.send_msg(flow_mod)

    def get_topology_data(self):
        switches_list = get_all_switch(self)
        links_list = get_all_link(self)
        hosts_list = get_host(self, 1)
        print(hosts_list)
        self.network_graph = {'switches': [], 'links': [], 'hosts': []}

        # Retrieve switch information
        for switch in switches_list:
            switch_dict = {'dpid': switch.dp.id, 'ports': []}
            for port in switch.ports:
                switch_dict['ports'].append(port.port_no)
            self.network_graph['switches'].append(switch_dict)

        # Retrieve host information
        for host in hosts_list:
            host_dict = {'mac': host.mac, 'ip': host.ipv4[0], 'port': host.port}
            self.network_graph['hosts'].append(host_dict)
            
        # Retrieve link information
        for link in links_list:
            link_dict = {'src': link.src.dpid, 'src_port': link.src.port_no, 'dst': link.dst.dpid, 'dst_port': link.dst.port_no, 'cost': 0}
            self.network_graph['links'].append(link_dict)
        self.set_random_link_costs()
        print(self.network_graph)

    def install_forwarding_rules(self):
        parser = self.dp.ofproto_parser

        for i in range(len(self.path) - 1):
            node1, node2 = self.path[i], self.path[i + 1]

            # Retrieve the datapath object for the current switch
            datapath = self.get_datapath(node1)

            # Create the match and actions for the flow entry
            match = parser.OFPMatch()
            actions = [parser.OFPActionOutput(self.network_graph['links'][(node1, node2)]['src_port'])]

            # Install the flow entry in the switch
            self.add_flow(datapath, 1, match, actions)



    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        parser = datapath.ofproto_parser
        # Parse the incoming packet
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
    
        if eth.ethertype == ether_types.ETH_TYPE_IP:  # IPv4 packets only
            src_ip = eth.src
            dst_ip = eth.dst
            self.set_random_link_costs()  # Update link costs
            print("salam")
            # Get best path from source to destination
            src_node = int(src_ip.split('.')[-1])
            dst_node = int(dst_ip.split('.')[-1])
            self.path = self.get_best_path(src_node, dst_node)

            # Install forwarding rules for the path
            self.install_forwarding_rules()

            # Forward the packet to the appropriate output port
            actions = [parser.OFPActionOutput(self.network_graph['links'][(self.path[0], self.path[1])]['src_port'])]
            out_port = self.network_graph['hosts'][dst_ip]['port']
            actions.append(parser.OFPActionOutput(out_port))

            # Send the packet out
            data = msg.data
            out = parser.OFPPacketOut(datapath=datapath, buffer_id=datapath.ofproto.OFP_NO_BUFFER,
                                    in_port=msg.match['in_port'], actions=actions, data=data)
            datapath.send_msg(out)


    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]

        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)
