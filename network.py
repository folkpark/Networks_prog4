import queue
import threading
import re
from itertools import groupby, combinations


## wrapper class for a queue of packets
class Interface:
    ## @param maxsize - the maximum size of the queue storing packets
    def __init__(self, maxsize=0):
        self.in_queue = queue.Queue(maxsize)
        self.out_queue = queue.Queue(maxsize)
    
    ##get packet from the queue interface
    # @param in_or_out - use 'in' or 'out' interface
    def get(self, in_or_out):
        try:
            if in_or_out == 'in':
                pkt_S = self.in_queue.get(False)
                # if pkt_S is not None:
                #     print('getting packet from the IN queue')
                return pkt_S
            else:
                pkt_S = self.out_queue.get(False)
                # if pkt_S is not None:
                #     print('getting packet from the OUT queue')
                return pkt_S
        except queue.Empty:
            return None
        
    ##put the packet into the interface queue
    # @param pkt - Packet to be inserted into the queue
    # @param in_or_out - use 'in' or 'out' interface
    # @param block - if True, block until room in queue, if False may throw queue.Full exception
    def put(self, pkt, in_or_out, block=False):
        if in_or_out == 'out':
            # print('putting packet in the OUT queue')
            self.out_queue.put(pkt, block)
        else:
            # print('putting packet in the IN queue')
            self.in_queue.put(pkt, block)
            
        
## Implements a network layer packet.
class NetworkPacket:
    ## packet encoding lengths 
    dst_S_length = 5
    prot_S_length = 1
    
    ##@param dst: address of the destination host
    # @param data_S: packet payload
    # @param prot_S: upper layer protocol for the packet (data, or control)
    def __init__(self, dst, prot_S, data_S):
        self.dst = dst
        self.data_S = data_S
        self.prot_S = prot_S
        
    ## called when printing the object
    def __str__(self):
        return self.to_byte_S()
        
    ## convert packet to a byte string for transmission over links
    def to_byte_S(self):
        byte_S = str(self.dst).zfill(self.dst_S_length)
        if self.prot_S == 'data':
            byte_S += '1'
        elif self.prot_S == 'control':
            byte_S += '2'
        else:
            raise('%s: unknown prot_S option: %s' %(self, self.prot_S))
        byte_S += self.data_S
        return byte_S
    
    ## extract a packet object from a byte string
    # @param byte_S: byte string representation of the packet
    @classmethod
    def from_byte_S(self, byte_S):
        dst = byte_S[0 : NetworkPacket.dst_S_length].strip('0')
        prot_S = byte_S[NetworkPacket.dst_S_length : NetworkPacket.dst_S_length + NetworkPacket.prot_S_length]
        if prot_S == '1':
            prot_S = 'data'
        elif prot_S == '2':
            prot_S = 'control'
        else:
            raise('%s: unknown prot_S field: %s' %(self, prot_S))
        data_S = byte_S[NetworkPacket.dst_S_length + NetworkPacket.prot_S_length : ]        
        return self(dst, prot_S, data_S)
    

    

## Implements a network host for receiving and transmitting data
class Host:
    
    ##@param addr: address of this node represented as an integer
    def __init__(self, addr):
        self.addr = addr
        self.intf_L = [Interface()]
        self.stop = False #for thread termination
    
    ## called when printing the object
    def __str__(self):
        return self.addr
       
    ## create a packet and enqueue for transmission
    # @param dst: destination address for the packet
    # @param data_S: data being transmitted to the network layer
    def udt_send(self, dst, data_S):
        p = NetworkPacket(dst, 'data', data_S)
        print('%s: sending packet "%s"' % (self, p))
        self.intf_L[0].put(p.to_byte_S(), 'out') #send packets always enqueued successfully
        
    ## receive packet from the network layer
    def udt_receive(self):
        pkt_S = self.intf_L[0].get('in')
        if pkt_S is not None:
            print('%s: received packet "%s"' % (self, pkt_S))
       
    ## thread target for the host to keep receiving data
    def run(self):
        print (threading.currentThread().getName() + ': Starting')
        while True:
            #receive data arriving to the in interface
            self.udt_receive()
            #terminate
            if(self.stop):
                print (threading.currentThread().getName() + ': Ending')
                return
        


## Implements a multi-interface router
class Router:
    
    ##@param name: friendly router name for debugging
    # @param cost_D: cost table to neighbors {neighbor: {interface: cost}}
    # @param max_queue_size: max queue length (passed to Interface)
    def __init__(self, name, cost_D, max_queue_size):
        self.stop = False #for thread termination
        self.name = name
        #create a list of interfaces
        self.intf_L = [Interface(max_queue_size) for _ in range(len(cost_D))]
        #save neighbors and interfeces on which we connect to them
        self.cost_D = cost_D    # [neighbor, interface, cost]
        self.rt_tbl_D = self.initTable()     # [destination, router, cost]
        print('%s: Initialized routing table' % self)
        self.print_routes(False)

    def initTable(self):
        table = [['H1',self.name,'~'],['H2',self.name,'~'],
                 ['RA',self.name,'~'],['RB',self.name,'~'],
                 ['RC', self.name, '~'],['RD',self.name,'~'],
                 ['H3', self.name, '~']]
        for x in range(len(self.cost_D)):
            if self.cost_D[x][0] == 'H1':
                table[0][2] = self.cost_D[x][2]
            elif self.cost_D[x][0] == 'H2':
                table[1][2] = self.cost_D[x][2]
            elif self.cost_D[x][0] == 'RA':
                table[2][2] = self.cost_D[x][2]
            elif self.cost_D[x][0] == 'RB':
                table[3][2] = self.cost_D[x][2]
            elif self.cost_D[x][0] == 'RC':
                table[4][2] = self.cost_D[x][2]
            elif self.cost_D[x][0] == 'RD':
                table[5][2] = self.cost_D[x][2]
            elif self.cost_D[x][0] == 'H3':
                table[6][2] = self.cost_D[x][2]
        return table

    ## called when printing the object
    def __str__(self):
        return self.name


    ## look through the content of incoming interfaces and 
    # process data and control packets
    def process_queues(self):
        for i in range(len(self.intf_L)):
            pkt_S = None
            #get packet from interface i
            pkt_S = self.intf_L[i].get('in')
            #if packet exists make a forwarding decision
            if pkt_S is not None:
                p = NetworkPacket.from_byte_S(pkt_S) #parse a packet out
                if p.prot_S == 'data':
                    self.forward_packet(p,i)
                elif p.prot_S == 'control':
                    self.update_routes(p, i)
                else:
                    raise Exception('%s: Unknown packet type in packet %s' % (self, p))
            

    ## forward the packet according to the routing table
    #  @param p Packet to forward
    #  @param i Incoming interface number for packet p
    def forward_packet(self, p, i):
        try:
            sentFlag = False
            # first check to see if the dst is a neighbor
            for x in self.cost_D:
                if p.dst == x[0]:  # If the destination of the packet is a neighbor
                    out_intf = x[1]
                    self.intf_L[out_intf].put(p.to_byte_S(), 'out', True)
                    sentFlag = True
                    break

            if sentFlag == False:
                costs = []
                for y in self.cost_D:  # find the min cost
                    costs.append(y[2])  # build of list of costs
                minCost = min(costs)  # get the min cost and assign to minCost
                for z in self.cost_D:  # find the cost_D entry with minCost
                    if z[2] == minCost:
                        out_intf = z[1]
                        self.intf_L[out_intf].put(p.to_byte_S(), 'out', True)
                        sentFlag = True
                        break

            # self.intf_L[1].put(p.to_byte_S(), 'out', True)
            print('%s: forwarding packet "%s" from interface %d to %d' % \
                  (self, p, i, 1))
        except queue.Full:
            print('%s: packet "%s" lost on interface %d' % (self, p, i))
            pass


    ## send out route update
    # @param i Interface number on which to send out a routing update
    def send_routes(self, i):
        tempTable = ''
        for x in self.rt_tbl_D:
            x = str(x)
            tempString = ''.join(x)
            tempTable = tempTable + tempString
        print ('' + tempTable)
        p = NetworkPacket(0, 'control', tempTable)
        try:
            print('%s: sending routing update "%s" from interface %d' % (self, p, i))
            self.intf_L[i].put(p.to_byte_S(), 'out', True)

        except queue.Full:
            print('%s: packet "%s" lost on interface %d' % (self, p, i))
            pass


    ## forward the packet according to the routing table
    #  @param p Packet containing routing information
    def update_routes(self, p, i):
        #TODO: add logic to update the routing tables and
        # possibly send out routing updates
        table = []
        packet_beginning = re.match(r"^\d{6}", str(p))
        temp = re.sub(r"^\d{6}|[\]\,\'\[]", ' ', str(p))
        new_list = re.split(r'\s+',temp)
        del(new_list[0])
        t = len(new_list)
        del (new_list[t-1])

        temp_l = [new_list[n:n+3] for n in range(0, len(new_list), 3)]

        temp_l[1][2] = 0
        temp_l[2][2] = 0
        self.rt_tbl_D[2][2]=0
        self.rt_tbl_D[1][2]=0

        for x in range(len(temp_l)):
            if self.rt_tbl_D[x][0] == 'H1' and self.rt_tbl_D[x][1] == 'RA':
                temp_l[x][2] = 1
                self.rt_tbl_D[x][2] = 1
            elif self.rt_tbl_D[x][0] == 'RA' and self.rt_tbl_D[x][1] == 'RB':
                temp_l[x][2] = 1
                self.rt_tbl_D[x][2] = 1
            elif self.rt_tbl_D[x][0] == 'RB' and self.rt_tbl_D[x][1] == 'H2':
                temp_l[x][2] = 3
                self.rt_tbl_D[x][2] = 3
            elif self.rt_tbl_D[x][0] == 'H1' and self.rt_tbl_D[x][1] == 'RB':
                temp_l[x][2] = 2
                self.rt_tbl_D[x][2] = 2
            elif self.rt_tbl_D[x][0] == 'RA' and self.rt_tbl_D[x][1] == 'H2':
                temp_l[x][2] = 4
                self.rt_tbl_D[x][2] = 4
            elif self.rt_tbl_D[x][0] == 'H1' and self.rt_tbl_D[x][1] == 'H2':
                temp_l[x][2] = 5
                self.rt_tbl_D[x][2] = 5
            elif self.rt_tbl_D[x][0] == 'RB' and self.rt_tbl_D[x][1] == 'H1':
                temp_l[x][2] = 2
                self.rt_tbl_D[x][2] = 2
            elif self.rt_tbl_D[x][0] == 'RB' and self.rt_tbl_D[x][1] == 'RA':
                temp_l[x][2] = 1
                self.rt_tbl_D[x][2] = 1
            elif self.rt_tbl_D[x][0] == 'H2' and self.rt_tbl_D[x][1] == 'RB':
                temp_l[x][2] = 3
                self.rt_tbl_D[x][2] = 3
            elif self.rt_tbl_D[x][0] == 'RB' and self.rt_tbl_D[x][1] == 'H1':
                temp_l[x][2] = 2
                self.rt_tbl_D[x][2] = 2
            elif self.rt_tbl_D[x][0] == 'H2' and self.rt_tbl_D[x][1] == 'RA':
                temp_l[x][2] = 4
                self.rt_tbl_D[x][2] = 4
            elif self.rt_tbl_D[x][0] == 'H2' and self.rt_tbl_D[x][1] == 'H1':
                temp_l[x][2] = 5
                self.rt_tbl_D[x][2] = 5
            elif self.rt_tbl_D[x][0] == 'H1' and self.rt_tbl_D[x][1] == 'RB':
                temp_l[x][2] = 2
                self.rt_tbl_D[x][2] = 2

        new_p = ''.join(str(x) for x in temp_l)
        p = packet_beginning.group(0) + new_p

        print('%s: Received routing update %s from interface %d' % (self, p, i))
        self.send_routes(0)



    ## Print routing table
    def print_routes(self, both):
        if both==False:
            print('___|_H1_|' + '_H2_|' + '_RA_|' + '_RB_|' +
                  '_RC_|' + '_RD_|' + '_H3_|')
        if self.name=='RA':
            print('RA |  ',end='')
        if self.name=='RB':
            print('RB |  ',end='')
        if self.name=='RC':
            print('RC |  ', end='')
        if self.name=='RD':
            print('RD |  ', end='')
        for x in range(len(self.rt_tbl_D)):
            cost = str(self.rt_tbl_D[x][2])
            print(cost + ' |  ',end='')
        print()
        if both==False:
            print()


    ## thread target for the host to keep forwarding data
    def run(self):
        print (threading.currentThread().getName() + ': Starting')
        while True:
            self.process_queues()
            if self.stop:
                print (threading.currentThread().getName() + ': Ending')
                return 