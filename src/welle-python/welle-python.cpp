/* Copyright (C) 2024 Lamarqe
 *
 * This program is free software: you can redistribute it and/or modify it
 * under the terms of the GNU General Public License
 * as published by the Free Software Foundation, version 3.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty
 * of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
 * See the GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program. If not, see <https://www.gnu.org/licenses/>.
 */
#include <typeinfo>

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "backend/radio-receiver.h"
#include "input/input_factory.h"
#include "various/channels.h"

namespace py = pybind11;

class WavProgrammeHandler: public ProgrammeHandlerInterface {
public:
  /* Inherit the constructors */
  using ProgrammeHandlerInterface::ProgrammeHandlerInterface;

  virtual void onFrameErrors(int frameErrors) override
  {
//    PYBIND11_OVERRIDE_PURE_NAME(void, ProgrammeHandlerInterface, "on_frame_errors", onFrameErrors, frameErrors);
  }
  
  virtual void onNewAudio(std::vector<int16_t>&& audioData, int sampleRate, const std::string& mode) override
  {
    py::gil_scoped_acquire acquire;
    py::handle data = PyBytes_FromStringAndSize((const char*)audioData.data(), 2*audioData.size());
    PYBIND11_OVERRIDE_PURE_NAME(void, ProgrammeHandlerInterface, "on_new_audio", onNewAudio, data, sampleRate, mode);
  }

  virtual void onRsErrors(bool uncorrectedErrors, int numCorrectedErrors) override 
  {
//    PYBIND11_OVERRIDE_PURE_NAME(void, ProgrammeHandlerInterface, "on_rs_errors", onRsErrors, uncorrectedErrors, numCorrectedErrors);
  }
  
  virtual void onAacErrors(int aacErrors) override 
  {
//    PYBIND11_OVERRIDE_PURE_NAME(void, ProgrammeHandlerInterface, "on_aac_errors", onAacErrors, aacErrors);
  }
  
  virtual void onNewDynamicLabel(const std::string& label) override
  {
    PYBIND11_OVERRIDE_PURE_NAME(void, ProgrammeHandlerInterface, "on_new_dynamic_label", onNewDynamicLabel, label);
  }

  virtual void onMOT(const mot_file_t& mot_file) override
  {
    std::string mime_type;
    switch (mot_file.content_sub_type)
    {
      case 0x00: mime_type = "image/gif";  break;
      case 0x01: mime_type = "image/jpeg"; break;
      case 0x02: mime_type = "image/bmp";  break;
      case 0x03: mime_type = "image/png";  break;
      default:   mime_type = "unknown";
    }
    py::gil_scoped_acquire acquire;
    py::handle data = PyBytes_FromStringAndSize((const char*)mot_file.data.data(), mot_file.data.size());
    PYBIND11_OVERRIDE_PURE_NAME(void, ProgrammeHandlerInterface, "on_mot", onMOT, data, mime_type, mot_file.content_name);
  }
  
  virtual void onPADLengthError(size_t announced_xpad_len, size_t xpad_len) override
  {
//    PYBIND11_OVERRIDE_PURE_NAME(void, ProgrammeHandlerInterface, "on_pad_length_error", onPADLengthError, announced_xpad_len, xpad_len);
  }
};


class PythonRadioController : public RadioControllerInterface {
public:
  /* Inherit the constructors */
  using RadioControllerInterface::RadioControllerInterface;

  virtual void onSNR(float snr) override
  { 
//    PYBIND11_OVERRIDE_PURE_NAME(void, RadioControllerInterface, "on_snr", onSNR, snr);
  }

  virtual void onFrequencyCorrectorChange(int fine, int coarse) override 
  {
//    PYBIND11_OVERRIDE_PURE_NAME(void, RadioControllerInterface, "on_frequency_corrector_change", onFrequencyCorrectorChange, fine, coarse);
  }

  virtual void onSyncChange(char isSync) override 
  { 
    PYBIND11_OVERRIDE_PURE_NAME(void, RadioControllerInterface, "on_sync_change", onSyncChange, (bool) isSync);
  }
  virtual void onSignalPresence(bool isSignal) override
  { 
    PYBIND11_OVERRIDE_PURE_NAME(void, RadioControllerInterface, "on_signal_presence", onSignalPresence, isSignal);
  }

  virtual void onServiceDetected(uint32_t sId) override
  {
    PYBIND11_OVERRIDE_PURE_NAME(void, RadioControllerInterface, "on_service_detected", onServiceDetected, sId);
  }

  virtual void onNewEnsemble(uint16_t eId) override
  {
    PYBIND11_OVERRIDE_PURE_NAME(void, RadioControllerInterface, "on_new_ensemble", onNewEnsemble, eId);
  }

  virtual void onSetEnsembleLabel(DabLabel& label) override
  {
    PYBIND11_OVERRIDE_PURE_NAME(void, RadioControllerInterface, "on_set_ensemble_label", onSetEnsembleLabel, label.utf8_label());
  }

  virtual void onDateTimeUpdate(const dab_date_time_t& dateTime) override
  {
//    PYBIND11_OVERRIDE_PURE_NAME(void, RadioControllerInterface, "on_datetime_update", onDateTimeUpdate, dateTime);
  }

  virtual void onFIBDecodeSuccess(bool crcCheckOk, const uint8_t* fib) override 
  {
//    PYBIND11_OVERRIDE_PURE_NAME(void, RadioControllerInterface, "on_fib_decode_success", onFIBDecodeSuccess, crcCheckOk, fib);
  }
  
  virtual void onNewImpulseResponse(std::vector<float>&& data) override
  {
//    PYBIND11_OVERRIDE_PURE_NAME(void, RadioControllerInterface, "on_new_impulse_response", onNewImpulseResponse, data);
  }
  virtual void onNewNullSymbol(std::vector<DSPCOMPLEX>&& data) override
  {
//    PYBIND11_OVERRIDE_PURE_NAME(void, RadioControllerInterface, "on_new_null_symbol", onNewNullSymbol, data);
  }
  virtual void onConstellationPoints(std::vector<DSPCOMPLEX>&& data) override
  { 
//    PYBIND11_OVERRIDE_PURE_NAME(void, RadioControllerInterface, "on_constellation_points", onConstellationPoints, data);
  }

  virtual void onMessage(message_level_t level, const std::string& text, const std::string& text2 = std::string()) override
  {
//    PYBIND11_OVERRIDE_PURE_NAME(void, RadioControllerInterface, "on_message", onMessage, text, text2, level == message_level_t::Error);
  }

  virtual void onTIIMeasurement(tii_measurement_t&& m) override
  {
//    PYBIND11_OVERRIDE_PURE_NAME(void, RadioControllerInterface, "on_tii_measurement", onTIIMeasurement, m);
  }
};


class DabDevice {
  protected:
    RadioReceiver* rx = nullptr;
  public:
    PythonRadioController& controller;
    std::string deviceName;
    int gain;
    CVirtualInput* device = nullptr;
    DabDevice(PythonRadioController& radioController, std::string deviceNameParam, int gainParam):
              controller(radioController), deviceName(deviceNameParam), gain(gainParam)
      {
      }

    virtual bool initialize()
    {
      device = CInputFactory::GetDevice(controller, deviceName);
      if (device == nullptr)
      {
        return false;
      }
      if (device->getID() == CDeviceID::NULLDEVICE) {
        // We are not interested in a non-functional fallback device.
        py::gil_scoped_release release;
        delete device;
        device = nullptr;
        return false;
      }

      if (gain == -1) {
          device->setAgc(true);
      }
      else {
          device->setGain(gain);
      }
      return true;
    }

    virtual ~DabDevice() 
    {
    }
    
    virtual void close_device() 
    {
      py::gil_scoped_release release;
      if (device)
      {
        delete device;
        device = nullptr;
      }
    }

    virtual bool set_channel(std::string channel, bool isScan = false)
    {
      if (channel.empty())
      {
        if (rx)
        {
          py::gil_scoped_release release;
          device->stop();
          delete rx;
          rx = nullptr;
        }
        return true;
      }
      else
      {
        if (rx)
        {
          return false;
        }
        else
        {
          py::gil_scoped_release release;
          Channels channels;
          auto freq = channels.getFrequency(channel);
          device->setFrequency(freq);
          device->reset();

          RadioReceiverOptions rro;
          rro.decodeTII = true;
          rx = new RadioReceiver(controller, *device, rro);

          rx->restart(isScan);
          return true;
        }
      }
    }
    
    virtual bool subscribe_program(WavProgrammeHandler& handler, uint32_t sId)
    {
      if (!rx)
        return false;
      else
      {
        py::gil_scoped_release release;
        const Service& sadd = rx->getService(sId);
        return rx->addServiceToDecode(handler, "", sadd);
      }
    }

    virtual bool unsubscribe_program(uint32_t sId)
    {
      if (!rx)
        return false;
      else
      {
        py::gil_scoped_release release;
        const Service& sremove = rx->getService(sId);
        rx->removeServiceToDecode(sremove);
      }
      return true;
    }

    virtual std::optional<std::string> get_service_name(uint32_t sId)
    {
      py::gil_scoped_release release;
      const Service& srv = rx->getService(sId);
      if (srv.serviceId != 0) 
      {
        return srv.serviceLabel.utf8_label();
      }
      else
        return std::nullopt;
    }

    virtual bool is_audio_service(uint32_t sId)
    {
      py::gil_scoped_release release;
      const Service& srv = rx->getService(sId);
      if (srv.serviceId != 0) 
      {
        for (const ServiceComponent& sc : rx->getComponents(srv))
        {
          if (sc.transportMode() == TransportMode::Audio &&
              sc.audioType() == AudioServiceComponentType::DABPlus)
          return true;
        }
        return false;
      }
      else
        // service unknown
        return false;
    }
};

std::list<std::string> all_channel_names ()
{
  Channels chans;
  std::list<std::string> result;
  result.emplace_back(chans.getCurrentChannel());
  for (int i = 1; i < NUMBEROFCHANNELS; ++i)
  {
    result.emplace_back(chans.getNextChannel());
  }    
  return result; 
}


PYBIND11_MODULE(welle_py, m) 
{
  py::class_<ProgrammeHandlerInterface, WavProgrammeHandler>(m, "ProgrammeHandlerInterface")
     .def(py::init<>());

  py::class_<RadioControllerInterface, PythonRadioController>(m, "RadioControllerInterface")
     .def(py::init<>());

  py::class_<DabDevice>(m, "DabDeviceCpp")
     .def(py::init<PythonRadioController&, const std::string&, int>())
     .def("initialize", &DabDevice::initialize)
     .def("close_device", &DabDevice::close_device)
     .def("set_channel", &DabDevice::set_channel, py::arg("channel"), py::arg("isScan") = false)
     .def("subscribe_program", &DabDevice::subscribe_program)
     .def("unsubscribe_program", &DabDevice::unsubscribe_program)
     .def("get_service_name", &DabDevice::get_service_name)
     .def("is_audio_service", &DabDevice::is_audio_service)
     .def_readonly("device_name", &DabDevice::deviceName)
     .def_readonly("gain", &DabDevice::gain);

  m.def("all_channel_names", &all_channel_names);
}
