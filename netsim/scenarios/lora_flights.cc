/*
 * LoRaWAN EU868 with the signetlabdei lorawan module.
 *
 * Author: Huda Mueen.
 *
 * mode=toa      prints the module's LoRa time on air (LoraPhy::GetTimeOnAir)
 *               for PHY payload sizes given in --sizes, with the parameters the
 *               class A end device MAC uses (CR 4/5, 8 preamble symbols,
 *               explicit header, CRC on, low data rate optimisation at SF11 and
 *               SF12 with 125 kHz).
 * mode=flights  sends the fragments of a handshake through two class A end
 *               devices (A and B, one per side, each with its own duty cycle
 *               budget) as unconfirmed uplinks. The module's MAC enforces the
 *               EU868 duty cycle and the receive windows. A flight starts when
 *               the last frame of the previous flight has ended; no
 *               acknowledgement is simulated. Fragments: --flights "A:1251,B:3664"
 *               split into --cap byte pieces.
 *
 * Only sizes and times are simulated. Output lines are prefixed by "TOA," or
 * "FRAME," or "FLIGHTS,".
 */

#include "ns3/core-module.h"
#include "ns3/lorawan-module.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"
#include "ns3/propagation-module.h"

#include <iostream>
#include <sstream>
#include <vector>

using namespace ns3;
using namespace ns3::lorawan;

namespace
{

struct Frag
{
    int side;
    uint32_t bytes;
    int flight;
};

std::vector<Frag> g_frags;
size_t g_idx = 0;
Ptr<EndDeviceLorawanMac> g_mac[2];
uint8_t g_dr = 0;
Time g_firstStart;
Time g_lastEnd;
std::string g_tag;

LoraTxParameters
Params(uint8_t dr)
{
    LoraTxParameters p;
    p.spreadingFactor = 12 - dr; // EU868: DR0 SF12 ... DR5 SF7, 125 kHz
    p.bandwidthHz = 125000;
    p.codingRate = CodingRate::CR_4_5;
    p.lowDataRateOptimize = (p.spreadingFactor >= 11);
    p.preambleLenSymb = 8;
    p.implicitHeader = false;
    p.crcEnabled = true;
    return p;
}

void
SendNext()
{
    if (g_idx >= g_frags.size())
    {
        return;
    }
    const Frag& f = g_frags[g_idx];
    Ptr<Packet> p = Create<Packet>(f.bytes);
    g_mac[f.side]->Send(p);
}

void
OnStart(int side, Ptr<const Packet> pkt, uint32_t)
{
    if (g_idx >= g_frags.size())
    {
        return;
    }
    Time now = Simulator::Now();
    Time toa = LoraPhy::GetTimeOnAir(pkt->GetSize(), Params(g_dr));
    if (g_idx == 0)
    {
        g_firstStart = now;
    }
    g_lastEnd = now + toa;
    const Frag& f = g_frags[g_idx];
    std::cout << "FRAME," << g_tag << "," << unsigned(g_dr) << "," << g_idx << "," << f.flight
              << "," << (side == 0 ? "A" : "B") << "," << f.bytes << "," << pkt->GetSize() << ","
              << now.GetSeconds() << "," << toa.GetSeconds() << std::endl;
    size_t cur = g_idx;
    g_idx++;
    if (g_idx < g_frags.size())
    {
        if (g_frags[g_idx].flight == g_frags[cur].flight)
        {
            Simulator::ScheduleNow(&SendNext);
        }
        else
        {
            Simulator::Schedule(toa, &SendNext);
        }
    }
}

} // namespace

int
main(int argc, char** argv)
{
    std::string mode = "toa";
    std::string sizes = "13,20,30,40,50,64,100,150,200,235";
    std::string flights = "A:1251,B:3664";
    uint32_t cap = 51;
    uint32_t dr = 0;
    uint32_t seed = 20261021;
    uint32_t run = 1;
    CommandLine cmd(__FILE__);
    cmd.AddValue("mode", "toa or flights", mode);
    cmd.AddValue("sizes", "PHY payload sizes for mode=toa", sizes);
    cmd.AddValue("flights", "side:bytes list for mode=flights", flights);
    cmd.AddValue("cap", "application bytes per fragment", cap);
    cmd.AddValue("dr", "EU868 data rate index (0 to 5)", dr);
    cmd.AddValue("seed", "ns-3 global seed", seed);
    cmd.AddValue("run", "ns-3 run number", run);
    cmd.AddValue("tag", "free text copied to the output", g_tag);
    cmd.Parse(argc, argv);
    g_dr = dr;

    if (mode == "toa")
    {
        std::stringstream ss(sizes);
        std::string tok;
        while (std::getline(ss, tok, ','))
        {
            uint32_t n = std::stoul(tok);
            Time t = LoraPhy::GetTimeOnAir(n, Params(g_dr));
            std::cout << "TOA," << unsigned(g_dr) << "," << n << "," << t.GetSeconds() << std::endl;
        }
        return 0;
    }

    RngSeedManager::SetSeed(seed);
    RngSeedManager::SetRun(run);

    {
        std::stringstream ss(flights);
        std::string tok;
        int fl = 0;
        while (std::getline(ss, tok, ','))
        {
            int side = tok[0] == 'A' ? 0 : 1;
            uint32_t n = std::stoul(tok.substr(2));
            while (n > 0)
            {
                uint32_t b = std::min(n, cap);
                g_frags.push_back({side, b, fl});
                n -= b;
            }
            fl++;
        }
    }

    Ptr<LogDistancePropagationLossModel> loss = CreateObject<LogDistancePropagationLossModel>();
    loss->SetPathLossExponent(3.76);
    loss->SetReference(1, 7.7);
    Ptr<PropagationDelayModel> delay = CreateObject<ConstantSpeedPropagationDelayModel>();
    Ptr<LoraChannel> channel = CreateObject<LoraChannel>(loss, delay);

    MobilityHelper mobility;
    Ptr<ListPositionAllocator> alloc = CreateObject<ListPositionAllocator>();
    alloc->Add(Vector(100, 0, 0));
    alloc->Add(Vector(0, 100, 0));
    alloc->Add(Vector(0, 0, 0));
    mobility.SetPositionAllocator(alloc);
    mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");

    LoraPhyHelper phy;
    phy.SetChannel(channel);
    LorawanMacHelper mac;
    LoraHelper helper;

    NodeContainer eds;
    eds.Create(2);
    mobility.Install(eds);
    phy.SetDeviceType(LoraPhyHelper::ED);
    mac.SetDeviceType(LorawanMacHelper::ED_A);
    NetDeviceContainer edDevs = helper.Install(phy, mac, eds);

    NodeContainer gws;
    gws.Create(1);
    mobility.Install(gws);
    phy.SetDeviceType(LoraPhyHelper::GW);
    mac.SetDeviceType(LorawanMacHelper::GW);
    helper.Install(phy, mac, gws);

    for (int s = 0; s < 2; ++s)
    {
        Ptr<LoraNetDevice> d = DynamicCast<LoraNetDevice>(edDevs.Get(s));
        g_mac[s] = DynamicCast<EndDeviceLorawanMac>(d->GetMac());
        g_mac[s]->SetUplinkAdrBit(false);
        g_mac[s]->SetDataRate(g_dr);
        d->GetPhy()->TraceConnectWithoutContext("StartSending",
                                                MakeBoundCallback(&OnStart, s));
    }

    Simulator::Schedule(Seconds(1.0), &SendNext);
    Simulator::Stop(Hours(48));
    Simulator::Run();
    std::cout << "FLIGHTS," << g_tag << "," << unsigned(g_dr) << "," << cap << ","
              << g_frags.size() << "," << g_idx << "," << (g_lastEnd - g_firstStart).GetSeconds()
              << std::endl;
    Simulator::Destroy();
    return 0;
}
