from ryu.base import app_manager
from ryu.controller.handler import set_ev_cls
from ryu.topology import event
from ryu.ofproto import ofproto_v1_3
from ryu.ofproto import ofproto_v1_3_parser
from ryu.topology.api import get_switch, get_link
from ryu.app.wsgi import WSGIApplication, route
from webob import Response
import networkx as nx
import random

class MininetTopologyController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {'wsgi': WSGIApplication}

    def __init__(self, *args, **kwargs):
        super(MininetTopologyController, self).__init__(*args, **kwargs)
        self.topology_api_app = self
        self.network = nx.DiGraph()

        self.paths = {}

    @route('/best_paths', methods=['GET'], path='/best_paths')
    def get_best_paths(self, req, **kwargs):
        body = ''
        for src in self.network.nodes():
            for dst in self.network.nodes():
                if src != dst:
                    body += f'Best path from {src} to {dst}: {self.paths[src][dst]}\n'
        return Response(content_type='text/plain', body=body)

    @set_ev_cls(event.EventSwitchEnter)
    def get_topology_data(self, ev):
        switches = get_switch(self.topology_api_app, None)
        switches = [sw.dp.id for sw in switches]
        self.network.add_nodes_from(switches)

        link_list = get_link(self.topology_api_app, None)
        print('**************************************************')
        for link in link_list:
            w = random.randint(1, 10)
            print(link.src.dpid, link.dst.dpid, w)
            self.network.add_edge(link.src.dpid, link.dst.dpid, weight=w, port=link.src.port_no)
        print('-----------------------------------------------------')
        self.calculate_best_paths()
        self.create_forwarding_rules()

    def get_switch_by_port(self, port):
        switch_list = get_switch(self.topology_api_app, None)
        for switch in switch_list:
            for switch_port in switch.ports:
                if switch_port.port_no == port.port_no:
                    return switch
        return None

    
    def calculate_best_paths(self):
        self.paths = {}
        switches = self.network.nodes()
        for src in switches:
            self.paths[src] = {}
            for dst in switches:
                if src != dst:
                    self.paths[src][dst] = nx.shortest_path(self.network, src, dst)

    def create_forwarding_rules(self):
        for src in self.paths:
            for dst in self.paths[src]:
                path = self.paths[src][dst]
                in_port = self.network[src][path[1]]['port']
                out_port = self.network[path[-2]][dst]['port']

                # Create OpenFlow rules for switches in the path
                for i in range(1, len(path) - 1):
                    datapath = self.get_datapath(path[i])
                    parser = datapath.ofproto_parser
                    match = parser.OFPMatch(in_port=in_port)
                    actions = [parser.OFPActionOutput(out_port)]
                    self.add_flow(datapath, 1, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [ofproto_v1_3_parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match, instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)

    def get_datapath(self, dpid):
        switch_list = get_switch(self.topology_api_app, None)
        for switch in switch_list:
            if switch.dp.id == dpid:
                return switch.dp


def run():
    controller = MininetTopologyController()
    wsgi = WSGIApplication(controller)
    wsgi.register(controller)
    app_manager.run()


if __name__ == '__main__':
    run()
