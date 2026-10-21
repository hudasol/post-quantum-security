/*
 * IEEE 802.15.4 with 6LoWPAN: transfer of an object over a line of hops with
 * an application level selective repeat protocol that mirrors
 * linksim/sim.py selective_repeat (window of W segments, the last segment of
 * a window asks for a block acknowledgement with a bitmap, a timeout resends
 * the last segment as a poll, unacknowledged segments return to the pending
 * list).
 *
 * Author: Huda Mueen.
 *
 * Only sizes and times are simulated; payload bytes are filler. No
 * cryptographic operation is performed.
 *
 * Output: one CSV line on stdout, prefixed by "RESULT,"; the header is
 * printed with --header=1.
 */

#include "ns3/core-module.h"
#include "ns3/internet-module.h"
#include "ns3/lr-wpan-module.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"
#include "ns3/propagation-module.h"
#include "ns3/sixlowpan-module.h"
#include "ns3/spectrum-module.h"
#include "ns3/applications-module.h"

#include <algorithm>
#include <iostream>
#include <set>
#include <vector>

using namespace ns3;
using namespace ns3::lrwpan;

NS_LOG_COMPONENT_DEFINE("NetsimLrWpanSr");

namespace
{

// Scenario parameters
uint32_t g_objectBytes = 50000;
uint32_t g_segBytes = 64;
uint32_t g_window = 16;
double g_rtoFactor = 2.0;
double g_initRto = 1.0;
double g_minRto = 0.02;
uint32_t g_maxRetries = 20;
const uint16_t kPort = 6000;
const uint32_t kDataHdr = 10; // type 1, window id 2, seq 2, poll 1, lo 2, hi 2
const uint32_t kAckHdr = 7;   // type 1, window id 2, lo 2, nbits 2

// Sender state
Ptr<Socket> g_txSock;
Ipv6Address g_dst;
std::set<uint32_t> g_pending;
std::vector<uint32_t> g_win;
uint16_t g_winId = 0;
EventId g_rtoEv;
uint32_t g_polls = 0;
double g_srtt = -1.0;
double g_backoff = 1.0; // timer backoff, doubled after each expiry until a new sample
Time g_winSent;
Time g_start;
Time g_done;
bool g_completed = false;
bool g_failed = false;
uint64_t g_dataSent = 0;
uint64_t g_pollResends = 0;
uint64_t g_acksRx = 0;
uint32_t g_nseg = 0;

// Receiver state
Ptr<Socket> g_rxSock;
std::vector<bool> g_got;
uint64_t g_uniqueRx = 0;
uint64_t g_dupRx = 0;
uint64_t g_acksTx = 0;

// Counters from MAC and PHY traces
uint64_t g_phyTxLine = 0;
uint64_t g_phyTxAll = 0;
uint64_t g_macTxDrop = 0;
uint64_t g_macEnqSender = 0;

// Last PHY state of each line node and when it was entered, to detect a
// receiver that stays in BUSY_RX (a reception that never ends).
std::vector<PhyEnumeration> g_trx;
std::vector<double> g_trxSince;

void
Put16(uint8_t* b, uint16_t v)
{
    b[0] = v >> 8;
    b[1] = v & 0xff;
}

uint16_t
Get16(const uint8_t* b)
{
    return (uint16_t(b[0]) << 8) | b[1];
}

void
SendSeg(uint32_t seq, bool poll, uint32_t lo, uint32_t hi)
{
    uint32_t data = std::min(g_segBytes, g_objectBytes - seq * g_segBytes);
    std::vector<uint8_t> buf(kDataHdr + data, 0);
    buf[0] = 0;
    Put16(&buf[1], g_winId);
    Put16(&buf[3], seq);
    buf[5] = poll ? 1 : 0;
    Put16(&buf[6], lo);
    Put16(&buf[8], hi);
    Ptr<Packet> p = Create<Packet>(buf.data(), buf.size());
    g_txSock->SendTo(p, 0, Inet6SocketAddress(g_dst, kPort));
    g_dataSent++;
}

void OnRto();

void
ArmRto()
{
    double rto = g_backoff * ((g_srtt < 0) ? g_initRto : std::max(g_minRto, g_rtoFactor * g_srtt));
    g_rtoEv = Simulator::Schedule(Seconds(rto), &OnRto);
}

void
StartWindow()
{
    if (g_pending.empty())
    {
        g_completed = true;
        g_done = Simulator::Now();
        Simulator::Stop();
        return;
    }
    g_win.clear();
    for (uint32_t s : g_pending)
    {
        if (g_win.size() >= g_window)
        {
            break;
        }
        g_win.push_back(s);
    }
    g_winId++;
    g_polls = 0;
    uint32_t lo = g_win.front();
    uint32_t hi = g_win.back();
    for (size_t i = 0; i < g_win.size(); ++i)
    {
        SendSeg(g_win[i], i + 1 == g_win.size(), lo, hi);
    }
    g_winSent = Simulator::Now();
    ArmRto();
}

void
OnRto()
{
    g_polls++;
    if (g_polls > g_maxRetries)
    {
        g_failed = true;
        g_done = Simulator::Now();
        Simulator::Stop();
        return;
    }
    g_pollResends++;
    g_backoff *= 2.0;
    SendSeg(g_win.back(), true, g_win.front(), g_win.back());
    ArmRto();
}

void
SenderRecv(Ptr<Socket> s)
{
    Ptr<Packet> p;
    Address from;
    while ((p = s->RecvFrom(from)))
    {
        std::vector<uint8_t> b(p->GetSize());
        p->CopyData(b.data(), b.size());
        if (b.size() < kAckHdr || b[0] != 1)
        {
            continue;
        }
        uint16_t wid = Get16(&b[1]);
        if (wid != g_winId || g_completed || g_failed)
        {
            continue; // stale acknowledgement
        }
        g_acksRx++;
        g_rtoEv.Cancel();
        if (g_polls == 0)
        {
            double sample = (Simulator::Now() - g_winSent).GetSeconds();
            g_srtt = (g_srtt < 0) ? sample : 0.875 * g_srtt + 0.125 * sample;
            g_backoff = 1.0;
        }
        uint32_t lo = Get16(&b[3]);
        uint32_t nbits = Get16(&b[5]);
        for (uint32_t i = 0; i < nbits; ++i)
        {
            uint32_t byte = kAckHdr + i / 8;
            if (byte < b.size() && (b[byte] >> (7 - i % 8)) & 1)
            {
                g_pending.erase(lo + i);
            }
        }
        StartWindow();
    }
}

void
ReceiverRecv(Ptr<Socket> s)
{
    Ptr<Packet> p;
    Address from;
    while ((p = s->RecvFrom(from)))
    {
        std::vector<uint8_t> b(p->GetSize());
        p->CopyData(b.data(), b.size());
        if (b.size() < kDataHdr || b[0] != 0)
        {
            continue;
        }
        uint16_t wid = Get16(&b[1]);
        uint32_t seq = Get16(&b[3]);
        bool poll = b[5] != 0;
        uint32_t lo = Get16(&b[6]);
        uint32_t hi = Get16(&b[8]);
        if (seq < g_got.size())
        {
            if (g_got[seq])
            {
                g_dupRx++;
            }
            else
            {
                g_got[seq] = true;
                g_uniqueRx++;
            }
        }
        if (poll && hi >= lo)
        {
            uint32_t nbits = hi - lo + 1;
            std::vector<uint8_t> a(kAckHdr + (nbits + 7) / 8, 0);
            a[0] = 1;
            Put16(&a[1], wid);
            Put16(&a[3], lo);
            Put16(&a[5], nbits);
            for (uint32_t i = 0; i < nbits; ++i)
            {
                if (lo + i < g_got.size() && g_got[lo + i])
                {
                    a[kAckHdr + i / 8] |= (1 << (7 - i % 8));
                }
            }
            Ptr<Packet> ap = Create<Packet>(a.data(), a.size());
            s->SendTo(ap, 0, from);
            g_acksTx++;
        }
    }
}

void
PhyTxLine(Ptr<const Packet>)
{
    g_phyTxLine++;
}

void
PhyTxAll(Ptr<const Packet>)
{
    g_phyTxAll++;
}

void
MacDrop(Ptr<const Packet>)
{
    g_macTxDrop++;
}

void
TrxChange(uint32_t i, PhyEnumeration, PhyEnumeration now)
{
    g_trx[i] = now;
    g_trxSince[i] = Simulator::Now().GetSeconds();
}

void
MacEnqSender(Ptr<const Packet>)
{
    g_macEnqSender++;
}

void
WarmUp(Ptr<Socket> s, Ipv6Address to, uint16_t port)
{
    uint8_t b[4] = {2, 0, 0, 0};
    s->SendTo(Create<Packet>(b, 4), 0, Inet6SocketAddress(to, port));
}

void
StartTransfer()
{
    g_start = Simulator::Now();
    StartWindow();
}

} // namespace

int
main(int argc, char** argv)
{
    uint32_t hops = 1;
    uint32_t bgNodes = 0;
    double bgInterval = 0.1;
    uint32_t bgBytes = 50;
    double spacing = 20.0;
    double bgY = 10.0;
    uint32_t minBe = 3;
    uint32_t maxBe = 5;
    uint32_t maxBackoffs = 4;
    uint32_t retries = 3;
    uint32_t seed = 20261021;
    uint32_t run = 1;
    double maxSimTime = 3600.0;
    bool header = false;
    std::string tag = "";

    CommandLine cmd(__FILE__);
    cmd.AddValue("hops", "number of hops (line of hops+1 nodes)", hops);
    cmd.AddValue("bgNodes", "neighbours sending background traffic (each to its own partner)", bgNodes);
    cmd.AddValue("bgInterval", "seconds between background packets per neighbour", bgInterval);
    cmd.AddValue("bgBytes", "background UDP payload bytes", bgBytes);
    cmd.AddValue("spacing", "metres between adjacent line nodes", spacing);
    cmd.AddValue("bgY", "distance of background neighbours from the line, metres", bgY);
    cmd.AddValue("minBe", "macMinBE", minBe);
    cmd.AddValue("maxBe", "macMaxBE", maxBe);
    cmd.AddValue("maxBackoffs", "macMaxCSMABackoffs", maxBackoffs);
    cmd.AddValue("retries", "macMaxFrameRetries", retries);
    cmd.AddValue("objectBytes", "object size in bytes", g_objectBytes);
    cmd.AddValue("segBytes", "object bytes per segment (UDP datagram)", g_segBytes);
    cmd.AddValue("window", "selective repeat window in segments", g_window);
    cmd.AddValue("rtoFactor", "timeout as a multiple of the smoothed window round trip", g_rtoFactor);
    cmd.AddValue("maxRetries", "polls per window before the transfer is declared failed", g_maxRetries);
    cmd.AddValue("seed", "ns-3 global seed", seed);
    cmd.AddValue("run", "ns-3 run number (independent substream)", run);
    cmd.AddValue("maxSimTime", "simulation cap in seconds", maxSimTime);
    cmd.AddValue("tag", "free text copied to the output", tag);
    cmd.AddValue("header", "print the CSV header and exit", header);
    cmd.Parse(argc, argv);

    if (header)
    {
        std::cout << "RESULT,tag,hops,bg_nodes,bg_interval_s,bg_bytes,spacing_m,min_be,max_be,"
                     "max_backoffs,frame_retries,object_bytes,seg_bytes,window,seed,run,"
                     "completed,time_s,segments,data_sent,poll_resends,unique_rx,dup_rx,acks_tx,"
                     "acks_rx,mac_frames_enqueued_sender,phy_tx_line,phy_tx_all,mac_tx_drop,stuck_rx_nodes,stuck_rx_since_s"
                  << std::endl;
        return 0;
    }

    RngSeedManager::SetSeed(seed);
    RngSeedManager::SetRun(run);

    NodeContainer line;
    line.Create(hops + 1);
    NodeContainer bg;
    bg.Create(2 * bgNodes);
    NodeContainer all;
    all.Add(line);
    all.Add(bg);

    Ptr<ListPositionAllocator> pos = CreateObject<ListPositionAllocator>();
    for (uint32_t i = 0; i <= hops; ++i)
    {
        pos->Add(Vector(i * spacing, 0.0, 0.0));
    }
    Ptr<UniformRandomVariable> ux = CreateObject<UniformRandomVariable>();
    ux->SetStream(7);
    for (uint32_t j = 0; j < bgNodes; ++j)
    {
        double x = ux->GetValue(0.0, hops * spacing);
        pos->Add(Vector(x, bgY, 0.0));
        pos->Add(Vector(x + 5.0, bgY, 0.0));
    }
    MobilityHelper mob;
    mob.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mob.SetPositionAllocator(pos);
    mob.Install(all);

    LrWpanHelper lr;
    lr.SetPropagationDelayModel("ns3::ConstantSpeedPropagationDelayModel");
    lr.AddPropagationLossModel("ns3::LogDistancePropagationLossModel");
    NetDeviceContainer lrDevs = lr.Install(all);
    int64_t stream = 100;
    stream += lr.AssignStreams(lrDevs, stream);
    stream += lr.GetChannel()->AssignStreams(stream);
    lr.CreateAssociatedPan(lrDevs, 1);

    g_trx.assign(hops + 1, IEEE_802_15_4_PHY_TRX_OFF);
    g_trxSince.assign(hops + 1, 0.0);
    for (uint32_t i = 0; i < lrDevs.GetN(); ++i)
    {
        Ptr<LrWpanNetDevice> d = DynamicCast<LrWpanNetDevice>(lrDevs.Get(i));
        Ptr<LrWpanCsmaCa> c = d->GetCsmaCa();
        c->SetMacMaxBE(maxBe);
        c->SetMacMinBE(minBe);
        c->SetMacMaxCSMABackoffs(maxBackoffs);
        d->GetMac()->SetMacMaxFrameRetries(retries);
        d->GetPhy()->TraceConnectWithoutContext("PhyTxBegin", MakeCallback(&PhyTxAll));
        if (i <= hops)
        {
            d->GetPhy()->TraceConnectWithoutContext("PhyTxBegin", MakeCallback(&PhyTxLine));
            d->GetMac()->TraceConnectWithoutContext("MacTxDrop", MakeCallback(&MacDrop));
            d->GetPhy()->TraceConnectWithoutContext("TrxStateValue", MakeBoundCallback(&TrxChange, i));
        }
        if (i == 0)
        {
            d->GetMac()->TraceConnectWithoutContext("MacTxEnqueue", MakeCallback(&MacEnqSender));
        }
    }

    InternetStackHelper inet;
    inet.SetIpv4StackInstall(false);
    inet.Install(all);
    stream += inet.AssignStreams(all, stream);

    SixLowPanHelper six;
    NetDeviceContainer devs = six.Install(lrDevs);
    stream += six.AssignStreams(devs, stream);

    Ipv6AddressHelper ip;
    ip.SetBase(Ipv6Address("2001:2::"), Ipv6Prefix(64));
    Ipv6InterfaceContainer ifs = ip.Assign(devs);

    // Static routes along the line, both directions; relays forward.
    Ipv6StaticRoutingHelper srh;
    for (uint32_t i = 0; i <= hops; ++i)
    {
        Ptr<Ipv6> ipv6 = line.Get(i)->GetObject<Ipv6>();
        Ptr<Ipv6StaticRouting> r = srh.GetStaticRouting(ipv6);
        uint32_t ifIndex = ipv6->GetInterfaceForDevice(devs.Get(i));
        if (i > 0 && i < hops)
        {
            ipv6->SetForwarding(ifIndex, true);
        }
        if (i < hops)
        {
            r->AddHostRouteTo(ifs.GetAddress(hops, 1), ifs.GetAddress(i + 1, 1), ifIndex);
        }
        if (i > 0)
        {
            r->AddHostRouteTo(ifs.GetAddress(0, 1), ifs.GetAddress(i - 1, 1), ifIndex);
        }
    }
    NeighborCacheHelper nch;
    nch.PopulateNeighborCache();

    // Background traffic: each neighbour sends to its own partner.
    Ptr<UniformRandomVariable> us = CreateObject<UniformRandomVariable>();
    us->SetStream(8);
    for (uint32_t j = 0; j < bgNodes; ++j)
    {
        uint32_t a = hops + 1 + 2 * j;
        uint32_t b = a + 1;
        UdpServerHelper srv(9000 + j);
        ApplicationContainer sa = srv.Install(all.Get(b));
        sa.Start(Seconds(0.0));
        UdpClientHelper cli(ifs.GetAddress(b, 1), 9000 + j);
        cli.SetAttribute("MaxPackets", UintegerValue(0));
        cli.SetAttribute("Interval", TimeValue(Seconds(bgInterval)));
        cli.SetAttribute("PacketSize", UintegerValue(bgBytes));
        ApplicationContainer ca = cli.Install(all.Get(a));
        ca.Start(Seconds(0.5 + us->GetValue(0.0, bgInterval)));
    }

    // Selective repeat endpoints
    g_nseg = (g_objectBytes + g_segBytes - 1) / g_segBytes;
    for (uint32_t s = 0; s < g_nseg; ++s)
    {
        g_pending.insert(s);
    }
    g_got.assign(g_nseg, false);
    g_dst = ifs.GetAddress(hops, 1);
    TypeId tid = TypeId::LookupByName("ns3::UdpSocketFactory");
    g_rxSock = Socket::CreateSocket(line.Get(hops), tid);
    g_rxSock->Bind(Inet6SocketAddress(Ipv6Address::GetAny(), kPort));
    g_rxSock->SetRecvCallback(MakeCallback(&ReceiverRecv));
    g_txSock = Socket::CreateSocket(line.Get(0), tid);
    g_txSock->Bind(Inet6SocketAddress(Ipv6Address::GetAny(), kPort + 1));
    g_txSock->SetRecvCallback(MakeCallback(&SenderRecv));

    // One small datagram each way before the transfer, so that no first
    // window segment waits for address resolution.
    Simulator::Schedule(Seconds(0.3), &WarmUp, g_txSock, g_dst, kPort);
    Simulator::Schedule(Seconds(0.6), &WarmUp, g_rxSock, ifs.GetAddress(0, 1), kPort + 1);
    Simulator::Schedule(Seconds(1.0), &StartTransfer);
    Simulator::Stop(Seconds(1.0 + maxSimTime));
    Simulator::Run();
    if (!g_completed && !g_failed)
    {
        g_done = Simulator::Now();
    }
    double t = (g_done - g_start).GetSeconds();
    double tEnd = Simulator::Now().GetSeconds();
    uint32_t stuck = 0;
    double stuckSince = -1.0;
    for (uint32_t i = 0; i <= hops; ++i)
    {
        if (g_trx[i] == IEEE_802_15_4_PHY_BUSY_RX && tEnd - g_trxSince[i] > 1.0)
        {
            stuck++;
            stuckSince = (stuckSince < 0) ? g_trxSince[i] : std::min(stuckSince, g_trxSince[i]);
        }
    }
    std::cout << "RESULT," << tag << "," << hops << "," << bgNodes << "," << bgInterval << ","
              << bgBytes << "," << spacing << "," << minBe << "," << maxBe << "," << maxBackoffs
              << "," << retries << "," << g_objectBytes << "," << g_segBytes << "," << g_window
              << "," << seed << "," << run << "," << (g_completed ? 1 : 0) << "," << t << ","
              << g_nseg << "," << g_dataSent << "," << g_pollResends << "," << g_uniqueRx << ","
              << g_dupRx << "," << g_acksTx << "," << g_acksRx << "," << g_macEnqSender << ","
              << g_phyTxLine << "," << g_phyTxAll << "," << g_macTxDrop << "," << stuck << ","
              << stuckSince << std::endl;
    Simulator::Destroy();
    return 0;
}
