/*
 *    Copyright (C) 2018
 *    Matthias P. Braendli (matthias.braendli@mpb.li)
 *
 *    Copyright (C) 2017
 *    Albrecht Lohofener (albrechtloh@gmx.de)
 *
 *    This file is part of the welle.io.
 *    Many of the ideas as implemented in welle.io are derived from
 *    other work, made available through the GNU general Public License.
 *    All copyrights of the original authors are recognized.
 *
 *    welle.io is free software; you can redistribute it and/or modify
 *    it under the terms of the GNU General Public License as published by
 *    the Free Software Foundation; either version 2 of the License, or
 *    (at your option) any later version.
 *
 *    welle.io is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *    GNU General Public License for more details.
 *
 *    You should have received a copy of the GNU General Public License
 *    along with welle.io; if not, write to the Free Software
 *    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 *
 */

#include "dab-constants.h"
#include <iostream>
#include <exception>
#include <sstream>

using namespace std;

// Table ETSI EN 300 401 Page 50
// Table is copied from the work of Michael Hoehn
const int ProtLevel[64][3] = {
    {16,5,32},  // Index 0
    {21,4,32},
    {24,3,32},
    {29,2,32},
    {35,1,32},  // Index 4
    {24,5,48},
    {29,4,48},
    {35,3,48},
    {42,2,48},
    {52,1,48},  // Index 9
    {29,5,56},
    {35,4,56},
    {42,3,56},
    {52,2,56},
    {32,5,64},  // Index 14
    {42,4,64},
    {48,3,64},
    {58,2,64},
    {70,1,64},
    {40,5,80},  // Index 19
    {52,4,80},
    {58,3,80},
    {70,2,80},
    {84,1,80},
    {48,5,96},  // Index 24
    {58,4,96},
    {70,3,96},
    {84,2,96},
    {104,1,96},
    {58,5,112}, // Index 29
    {70,4,112},
    {84,3,112},
    {104,2,112},
    {64,5,128},
    {84,4,128}, // Index 34
    {96,3,128},
    {116,2,128},
    {140,1,128},
    {80,5,160},
    {104,4,160},    // Index 39
    {116,3,160},
    {140,2,160},
    {168,1,160},
    {96,5,192},
    {116,4,192},    // Index 44
    {140,3,192},
    {168,2,192},
    {208,1,192},
    {116,5,224},
    {140,4,224},    // Index 49
    {168,3,224},
    {208,2,224},
    {232,1,224},
    {128,5,256},
    {168,4,256},    // Index 54
    {192,3,256},
    {232,2,256},
    {280,1,256},
    {160,5,320},
    {208,4,320},    // index 59
    {280,2,320},
    {192,5,384},
    {280,3,384},
    {416,1,384}};


static std::string flag_to_shortlabel(const std::string& label, uint16_t flag)
{
    stringstream shortlabel;
    for (size_t i = 0; i < label.size(); ++i) {
        if (flag & 0x8000 >> i) {
            shortlabel << label[i];
        }
    }

    return shortlabel.str();
}

string DabLabel::utf8_label() const
{
    const auto fig2 = fig2_label();
    if (not fig2.empty()) {
        return fig2;
    }
    else {
        return fig1_label_utf8();
    }
}

string DabLabel::fig1_label_utf8() const
{
    return toUtf8StringUsingCharset(fig1_label.c_str(), charset);
}

string DabLabel::fig1_shortlabel_utf8() const
{
    const string shortlabel = flag_to_shortlabel(fig1_label, fig1_flag);
    return toUtf8StringUsingCharset(shortlabel.c_str(), charset);
}

void DabLabel::setCharset(uint8_t charset_id)
{
    charset = static_cast<CharacterSet>(charset_id);
}

string DabLabel::fig2_label() const
{
    vector<uint8_t> segments_cat;
    for (size_t i = 0; i < segment_count; i++) {
        if (segments.count(i) == 0) {
            return "";
        }
        else {
            const auto& s = segments.at(i);
            copy(s.begin(), s.end(), back_inserter(segments_cat));
        }
    }

    switch (extended_label_charset) {
        case CharacterSet::EbuLatin:
            std::clog << "DABConstants: FIG2 label encoded in EBU Latin is not allowed." << std::endl;
            return ""; // Fallback to FIG1
        case CharacterSet::UnicodeUtf8:
            return string(segments_cat.begin(), segments_cat.end());
        case CharacterSet::UnicodeUcs2:
            return toUtf8StringUsingCharset(
                    segments_cat.data(), CharacterSet::UnicodeUcs2, segments_cat.size());
        case CharacterSet::Undefined:
            return "";
    }
    throw logic_error("invalid extended label charset " + to_string((int)extended_label_charset));
}

DABParams::DABParams(int mode)
{
    setMode(mode);
}

void DABParams::setMode(int mode)
{
    switch (mode)
    {
        case 1:
            dabMode = 1;
            L = 76;
            K = 1536;
            T_F = 196608;
            T_null = 2656;
            T_s = 2552;
            T_u = 2048;
            guardLength = 504;
            carrierDiff = 1000;
            break;

        case 2:
            dabMode = 2;
            L = 76;
            K = 384;
            T_null = 664;
            T_F = 49152;
            T_s = 638;
            T_u = 512;
            guardLength = 126;
            carrierDiff = 4000;
            break;

        case 3:
            dabMode = 3;
            L = 153;
            K = 192;
            T_F = 49152;
            T_null = 345;
            T_s = 319;
            T_u = 256;
            guardLength = 63;
            carrierDiff = 2000;
            break;

        case 4:
            dabMode = 4;
            L = 76;
            K = 768;
            T_F = 98304;
            T_null = 1328;
            T_s = 1276;
            T_u = 1024;
            guardLength = 252;
            carrierDiff = 2000;
            break;

        default:
            throw out_of_range("Unknown mode " + to_string(mode));
    }
}

int Subchannel::bitrate() const
{
    const auto& ps = protectionSettings;
    if (ps.shortForm) {
        return ProtLevel[ps.uepTableIndex][2];
    }
    else {  // EEP
        switch (ps.eepProfile) {
            case EEPProtectionProfile::EEP_A:
                switch (ps.eepLevel) {
                    case EEPProtectionLevel::EEP_1:
                        return length / 12 * 8;
                    case EEPProtectionLevel::EEP_2:
                        return length / 8 * 8;
                    case EEPProtectionLevel::EEP_3:
                        return length / 6 * 8;
                    case EEPProtectionLevel::EEP_4:
                        return length / 4 * 8;
                }
                break;
            case EEPProtectionProfile::EEP_B:
                switch (ps.eepLevel) {
                    case EEPProtectionLevel::EEP_1:
                        return length / 27 * 32;
                    case EEPProtectionLevel::EEP_2:
                        return length / 21 * 32;
                    case EEPProtectionLevel::EEP_3:
                        return length / 18 * 32;
                    case EEPProtectionLevel::EEP_4:
                        return length / 15 * 32;
                }
                break;
        }
    }

    throw std::runtime_error("Unsupported protection");
}

int Subchannel::numCU() const
{
    const auto& ps = protectionSettings;
    if (ps.shortForm) {
        return ProtLevel[ps.uepTableIndex][0];
    }
    else {
        switch (ps.eepProfile) {
            case EEPProtectionProfile::EEP_A:
                switch (ps.eepLevel) {
                    case EEPProtectionLevel::EEP_1:
                        return (bitrate() * 12) >> 3;
                    case EEPProtectionLevel::EEP_2:
                        return bitrate();
                    case EEPProtectionLevel::EEP_3:
                        return (bitrate() * 6) >> 3;
                    case EEPProtectionLevel::EEP_4:
                        return (bitrate() >> 1);
                }
                break;
            case EEPProtectionProfile::EEP_B:
                switch (ps.eepLevel) {
                    case EEPProtectionLevel::EEP_1:
                        return (bitrate() * 27) >> 5;
                    case EEPProtectionLevel::EEP_2:
                        return (bitrate() * 21) >> 5;
                    case EEPProtectionLevel::EEP_3:
                        return (bitrate() * 18) >> 5;
                    case EEPProtectionLevel::EEP_4:
                        return (bitrate() * 15) >> 5;
                }
                break;
        }
    }
    return -1;
}

string Subchannel::protection() const
{
    string prot;
    const auto& ps = protectionSettings;
    if (ps.shortForm) {
        prot = "UEP " + to_string((int)ps.uepLevel);
    }
    else {  // EEP
        prot = "EEP ";
        switch (ps.eepProfile) {
            case EEPProtectionProfile::EEP_A:
                prot += to_string((int)ps.eepLevel) + "-A";
                break;
            case EEPProtectionProfile::EEP_B:
                prot += to_string((int)ps.eepLevel) + "-B";
                break;
        }
    }
    return prot;
}

TransportMode ServiceComponent::transportMode() const
{
    if (TMid == 0) {
        return TransportMode::Audio;
    }
    else if (TMid == 1) {
        return TransportMode::StreamData;
    }
    else if (TMid == 2) {
        return TransportMode::FIDC;
    }
    else if (TMid == 3) {
        return TransportMode::PacketData;
    }
    throw std::logic_error("Illegal TMid!");
}

AudioServiceComponentType ServiceComponent::audioType() const
{
    if (ASCTy == 63) {
        return AudioServiceComponentType::DABPlus;
    }
    else {
        return AudioServiceComponentType::Unknown;
    }
}

