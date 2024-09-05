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

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "backend/radio-receiver.h"
#include "input/input_factory.h"
#include "various/channels.h"

namespace py = pybind11;

#define RUN_IN_ASYNC(cname, name, ...)                                                        \
  py::gil_scoped_acquire gil;                                                                 \
  py::function method = py::get_override(static_cast<const cname *>(this), name);             \
  py::module_::import("asyncio").attr("run_coroutine_threadsafe")(method(__VA_ARGS__), loop);

class ServiceEventHandler : public ProgrammeHandlerInterface {
public:
  virtual void onFrameErrors(int frameErrors) override {}
  virtual void onNewAudio(std::vector<int16_t>&& audioData, int sampleRate, const std::string& mode) override {}
  virtual void onRsErrors(bool uncorrectedErrors, int numCorrectedErrors) override  {}
  virtual void onAacErrors(int aacErrors) override {}
  virtual void onNewDynamicLabel(const std::string& label) override {}
  virtual void onMOT(const mot_file_t& mot_file) override {}
  virtual void onPADLengthError(size_t announced_xpad_len, size_t xpad_len) override {}
  virtual void ProcessUntouchedStream(const uint8_t* /*data*/, size_t /*len*/, size_t /*duration_ms*/) override {}
};

class PyServiceEventHandler: public ServiceEventHandler {
protected:
  py::object loop;

public:
  PyServiceEventHandler(): loop(py::module_::import("asyncio").attr("get_event_loop")())  {}

  virtual void ProcessUntouchedStream(const uint8_t* audioData, size_t len, size_t duration_ms) override 
  {
    py::gil_scoped_acquire acquire;
    py::bytes data((const char*)audioData, len);
    RUN_IN_ASYNC(ServiceEventHandler, "on_new_audio", data, 0, "aac");    
  }

  virtual void onNewAudio(std::vector<int16_t>&& audioData, int sampleRate, const std::string& mode) override
  {
    py::gil_scoped_acquire acquire;
    py::bytes data((const char*)audioData.data(), 2*audioData.size());
    RUN_IN_ASYNC(ServiceEventHandler, "on_new_audio", data, sampleRate, mode);
  }

  virtual void onNewDynamicLabel(const std::string& label) override
  {
    RUN_IN_ASYNC(ServiceEventHandler, "on_new_dynamic_label", label);
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
    py::bytes data((const char*)mot_file.data.data(), mot_file.data.size());
    RUN_IN_ASYNC(ServiceEventHandler, "on_mot", data, mime_type, mot_file.content_name);
  }  
};

class NullRadioController : public RadioControllerInterface {
public:
  virtual void onSNR(float snr) override {}
  virtual void onFrequencyCorrectorChange(int fine, int coarse) override  {}
  virtual void onSyncChange(char isSync) override  {}
  virtual void onSignalPresence(bool isSignal) override {}
  virtual void onServiceDetected(uint32_t sId) override {}
  virtual void onNewEnsemble(uint16_t eId) override {}
  virtual void onSetEnsembleLabel(DabLabel& label) override {}
  virtual void onDateTimeUpdate(const dab_date_time_t& dateTime) override {}
  virtual void onFIBDecodeSuccess(bool crcCheckOk, const uint8_t* fib) override  {}
  virtual void onNewImpulseResponse(std::vector<float>&& data) override {}
  virtual void onNewNullSymbol(std::vector<DSPCOMPLEX>&& data) override {}
  virtual void onConstellationPoints(std::vector<DSPCOMPLEX>&& data) override {}
  virtual void onMessage(message_level_t level, const std::string& text, const std::string& text2 = std::string()) override {}
  virtual void onTIIMeasurement(tii_measurement_t&& m) override {}
};

class DeviceMessageHandler : public NullRadioController {
protected:
  py::object logger;
public:
  DeviceMessageHandler(): logger(py::module_::import("logging").attr("getLogger")("DabDevice")) {}

  virtual void onMessage(message_level_t level, const std::string& text, const std::string& text2 = std::string()) override
  {
    std::string log_call(level == message_level_t::Error ? "error" : "info");
    if (!text.empty())
      logger.attr(log_call.c_str())(text);
    if (!text2.empty())
      logger.attr(log_call.c_str())(text2);
  }
};

class ChannelEventHandler : public NullRadioController {};
class PyChannelEventHandler : public ChannelEventHandler {
protected:
  py::object loop;

public:
  PyChannelEventHandler(): loop(py::module_::import("asyncio").attr("get_event_loop")())  {}

  virtual void onSyncChange(char isSync) override 
  { 
    bool syncBool = (bool) isSync;
    RUN_IN_ASYNC(ChannelEventHandler, "on_sync_change", syncBool);
  }
  virtual void onSignalPresence(bool isSignal) override
  { 
    RUN_IN_ASYNC(ChannelEventHandler, "on_signal_presence", isSignal);
  }

  virtual void onServiceDetected(uint32_t sId) override
  {
    RUN_IN_ASYNC(ChannelEventHandler, "on_service_detected", sId);
  }

  virtual void onNewEnsemble(uint16_t eId) override
  {
    RUN_IN_ASYNC(ChannelEventHandler, "on_new_ensemble", eId);
  }

  virtual void onSetEnsembleLabel(DabLabel& label) override
  {
    RUN_IN_ASYNC(ChannelEventHandler, "on_set_ensemble_label", label.utf8_label());
  }

  virtual void onMessage(message_level_t level, const std::string& text, const std::string& text2 = std::string()) override
  {
    RUN_IN_ASYNC(ChannelEventHandler, "on_message", text, text2, level == message_level_t::Error);
  }
};


class DabDevice {
  protected:
    RadioReceiver* rx = nullptr;
  public:
    std::string deviceName;
    int gain;
    bool decodeAudio;
    DeviceMessageHandler msgHandler;
    CVirtualInput* device = nullptr;
    py::object lock;
    DabDevice(std::string deviceNameParam = "auto", int gainParam = -1, bool decodeAudioParam = true):
        deviceName(deviceNameParam),
        gain(gainParam),
        decodeAudio(decodeAudioParam),
        msgHandler(DeviceMessageHandler()),
        lock(py::module_::import("threading").attr("Lock")()) {}

    virtual bool initialize()
    {
      device = CInputFactory::GetDevice(msgHandler, deviceName);
      if (device == nullptr)
        return false;

      if (device->getID() == CDeviceID::NULLDEVICE) 
      {
        // We are not interested in a non-functional fallback device.
        py::gil_scoped_release release;
        delete device;
        device = nullptr;
        return false;
      }

      if (gain == -1)
        device->setAgc(true);
      else
        device->setGain(gain);
      return true;
    }

    virtual ~DabDevice() 
    {
    }
    
    virtual void close_device() 
    {
      if (device)
      {
        py::gil_scoped_release release;
        delete device;
        device = nullptr;
      }
    }

    virtual void reset_channel()
    {
      if (rx)
      {
        py::gil_scoped_release release;
        device->stop();
        delete rx;
        rx = nullptr;
      }
    }

    virtual bool set_channel(std::string channel, ChannelEventHandler& handler, bool isScan = false)
    {
      if (rx)
        return false;

      py::gil_scoped_release release;
      Channels channels;
      auto freq = channels.getFrequency(channel);
      device->setFrequency(freq);
      device->reset();

      RadioReceiverOptions rro;
      rx = new RadioReceiver(handler, *device, rro, 1, decodeAudio);

      rx->restart(isScan);
      return true;
    }
    
    virtual std::optional<std::string> get_channel()
    {
      if (!rx)
        return std::nullopt;

      int frequency = device->getFrequency();
      try
      {
        Channels channels;
        return channels.getChannelForFrequency(frequency);
      }
      catch (std::out_of_range& e)
      {
        return std::nullopt;
      }
    }

    virtual bool subscribe_service(ServiceEventHandler& handler, uint32_t sId)
    {
      if (!rx)
        return false;

      py::gil_scoped_release release;
      const Service& sadd = rx->getService(sId);
      return rx->addServiceToDecode(handler, "", sadd);
    }

    virtual bool unsubscribe_service(uint32_t sId)
    {
      if (!rx)
        return false;

      py::gil_scoped_release release;
      const Service& sremove = rx->getService(sId);
      rx->removeServiceToDecode(sremove);
      return true;
    }

    virtual std::optional<std::string> get_service_name(uint32_t sId)
    {
      if (!rx)
        return std::nullopt;

      py::gil_scoped_release release;
      const Service& srv = rx->getService(sId);

      if (srv.serviceId != 0) 
        return srv.serviceLabel.utf8_label();
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
      }
      // service unknown
      return false;
    }

    const py::object getLock()
    {
      return lock;
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


PYBIND11_MODULE(welle_io, m) 
{
  py::class_<ServiceEventHandler, PyServiceEventHandler>(m, "ServiceEventHandler")
     .def(py::init<>());

  py::class_<ChannelEventHandler, PyChannelEventHandler>(m, "ChannelEventHandler")
     .def(py::init<>());

  py::class_<DabDevice>(m, "DabDevice")
     .def(py::init<const std::string&, int, bool>(), py::arg("device_name") = "auto", py::arg("gain") = -1, py::kw_only(), py::arg("decode_audio") = true)
     .def("initialize", &DabDevice::initialize)
     .def("close_device", &DabDevice::close_device)
     .def("set_channel", &DabDevice::set_channel, py::arg("channel"), py::arg("handler"), py::arg("isScan") = false)
     .def("get_channel", &DabDevice::get_channel)
     .def("reset_channel", &DabDevice::reset_channel)
     .def("subscribe_service", &DabDevice::subscribe_service)
     .def("unsubscribe_service", &DabDevice::unsubscribe_service)
     .def("get_service_name", &DabDevice::get_service_name)
     .def("is_audio_service", &DabDevice::is_audio_service)
     .def_readonly("device_name", &DabDevice::deviceName)
     .def_readonly("gain", &DabDevice::gain)
     .def_property_readonly("lock", &DabDevice::getLock);

  m.def("all_channel_names", &all_channel_names);
}
