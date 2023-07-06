from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.topo import Topo

class MyTopo(Topo):
    hosts_l = []
    switches_l = []
    switches_links = [
        (1, 8), (1, 3), (3, 8), (3, 6),
        (6, 8), (8, 7), (6, 5), (3, 4),
        (4, 5), (5, 2), (5, 7), (7, 2),
        (4, 2), (4, 7)
    ]
   
    def build(self):
        for i in range(1, 9):
            host = self.addHost('h' + str(i))
            switch = self.addSwitch('s' + str(i))
            self.hosts_l.append(host)
            self.switches_l.append(switch)
            self.addLink(switch, host, bw=1000, delay='1ms')
        for s_link, t_link in self.switches_links:
            self.addLink(self.switches_l[s_link - 1], self.switches_l[t_link - 1], bw=1000, delay='1ms')

setLogLevel('info')
topology = MyTopo()
net = Mininet(
    topo=topology,
    controller=RemoteController('c1', '127.0.0.1')
)
net.start()
CLI(net)
net.stop()