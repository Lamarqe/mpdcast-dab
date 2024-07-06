#include  <Python.h>

#include "backend/radio-receiver.h"
#include "input/input_factory.h"
#include "various/channels.h"
#include "ThreadPool.h"

extern "C" {
  PyObject* init_device         (PyObject *self, PyObject *args);
  PyObject* set_channel         (PyObject *self, PyObject *args);
  PyObject* subscribe_program   (PyObject *self, PyObject *args);
  PyObject* unsubscribe_program (PyObject *self, PyObject *args);
  PyObject* stop_device         (PyObject *self, PyObject *args);
  PyObject* finalize            (PyObject *self, PyObject *args);
  PyObject* get_service_name    (PyObject *self, PyObject *args);
  PyObject* PyInit_libwelle_py  (void);
}

class WavProgrammeHandler: public ProgrammeHandlerInterface {
  PyObject_HEAD

  protected:
    ThreadPool pool;
  public:
    PyObject* python_impl;

    WavProgrammeHandler(PyObject* pythonObj): pool(1)
    {
      std::cout << "Creating WavProgrammeHandler in C" << std::endl;
      this->python_impl = pythonObj;
      Py_XINCREF (python_impl);
    }

    virtual ~WavProgrammeHandler() 
    {
      Py_XDECREF (python_impl);
    }
    
    WavProgrammeHandler           (const WavProgrammeHandler& other)  = delete;
    WavProgrammeHandler& operator=(const WavProgrammeHandler& other)  = delete;
    WavProgrammeHandler           (      WavProgrammeHandler&& other) = default;
    WavProgrammeHandler& operator=(      WavProgrammeHandler&& other) = default;

    virtual void onFrameErrors(int frameErrors) override
    {
//      pool.enqueue([frameErrors, this]
//      {
//        PyGILState_STATE gstate  = PyGILState_Ensure ();
//        PyObject *result = PyObject_CallMethod (python_impl, "onFrameErrors", "(i)", frameErrors);
//
//        if (result)
//           Py_DECREF (result);
//        PyGILState_Release (gstate);
//      });
    }
    
    virtual void onNewAudio(std::vector<int16_t>&& audioData, int sampleRate, const std::string& mode) override
    {
      pool.enqueue([audioData, sampleRate, mode, this]
      {
        PyGILState_STATE gstate  = PyGILState_Ensure ();
        PyObject* data = PyBytes_FromStringAndSize((const char*)audioData.data(), 2*audioData.size());
        PyObject *result = PyObject_CallMethod (python_impl, "onNewAudio", "(Nis)", data,
                                                sampleRate, mode.c_str());
        if (result)
           Py_DECREF (result);
        PyGILState_Release (gstate);
      });
    }

    virtual void onRsErrors(bool uncorrectedErrors, int numCorrectedErrors) override 
    {
//      pool.enqueue([uncorrectedErrors, numCorrectedErrors, this]
//      {
//        PyGILState_STATE gstate  = PyGILState_Ensure ();
//        PyObject *result = PyObject_CallMethod (python_impl, "onRsErrors", "(bi)", uncorrectedErrors, numCorrectedErrors);
//
//        if (result)
//           Py_DECREF (result);
//        PyGILState_Release (gstate);
//      });
    }
    
    virtual void onAacErrors(int aacErrors) override 
    { 
//      pool.enqueue([aacErrors, this]
//      {
//        PyGILState_STATE gstate  = PyGILState_Ensure ();
//        PyObject *result = PyObject_CallMethod (python_impl, "onAacErrors", "(i)", aacErrors);
//
//        if (result)
//           Py_DECREF (result);
//        PyGILState_Release (gstate);
//      });
    }
    
    virtual void onNewDynamicLabel(const std::string& label) override
    {
      pool.enqueue([label, this]
      {
        PyGILState_STATE gstate  = PyGILState_Ensure ();
        PyObject *result = PyObject_CallMethod (python_impl, "onNewDynamicLabel", "(s)", label.c_str());

        if (result)
          Py_DECREF (result);
        PyGILState_Release (gstate);
      });
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
      pool.enqueue([mime_type, mot_file, this]
      {
        PyGILState_STATE gstate  = PyGILState_Ensure ();
        PyObject* data = PyBytes_FromStringAndSize((const char*)mot_file.data.data(), mot_file.data.size());
        PyObject *result = PyObject_CallMethod (python_impl, "onMOT", "(Nss)", data,
                                                mime_type.c_str(), mot_file.content_name.c_str());
        if (result != NULL)
          Py_DECREF (result);
        PyGILState_Release (gstate);
      });
    }
    
    virtual void onPADLengthError(size_t /*announced_xpad_len*/, size_t /*xpad_len*/) override
    {
      /* Not yet implemented */
    }

};


class PythonRadioController : public RadioControllerInterface {
  protected:
    RadioReceiver* rx = nullptr;
    ThreadPool pool;
  
  public:
    bool synced = false;
    PyObject* python_impl = nullptr;
    CVirtualInput* device = nullptr;
    std::map<uint32_t, WavProgrammeHandler*> programme_handlers;

    PythonRadioController(PyObject* pythonObj, const char* device_name, int gain): pool(1)
    {
      device = CInputFactory::GetDevice(*this, device_name);
      if (device == nullptr) {
          std::cout << "Could not start device" << std::endl;
          return;
      }
      this->python_impl = pythonObj;
      Py_XINCREF (python_impl);

      if (gain == -1) {
          device->setAgc(true);
      }
      else {
          device->setGain(gain);
      }
    }

    virtual ~PythonRadioController() 
    {
      Py_XDECREF (python_impl);
    }
    
    virtual void close_device() 
    {
      pool.enqueue([this]
      {
        if (device)
        {
          delete device;
          device = nullptr;
        }
      });
    }

    virtual bool set_channel(std::string channel)
    {
      if (channel.empty())
      {
        if (rx)
        {
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
          Channels channels;
          auto freq = channels.getFrequency(channel);
          device->setFrequency(freq);
          device->reset();

          RadioReceiverOptions rro;
          rro.decodeTII = true;
          rx = new RadioReceiver(*this, *device, rro);

          rx->restart(false);
          return true;
        }
      }
    }
    
    virtual bool subscribe_program(PyObject* python_handler, uint32_t sId)
    {
      if (!rx)
        return false;
      else
      {
        WavProgrammeHandler* c_handler = new WavProgrammeHandler(python_handler);
        programme_handlers.emplace(sId, c_handler);
        Service sadd = rx->getService(sId);
        return rx->addServiceToDecode(*c_handler, "", sadd);
      }
    }

    virtual bool unsubscribe_program(uint32_t sId)
    {
      if (!rx)
        return false;
      else
      {
        pool.enqueue([sId, this]
        {
          Service sremove = rx->getService(sId);
          rx->removeServiceToDecode(sremove);

          WavProgrammeHandler* handler = programme_handlers.at(sId);
          programme_handlers.erase(sId);
          delete handler;
        });
      }
      return true;
    }

    virtual PyObject* get_service_name(uint32_t sId)
    {
      Service srv = rx->getService(sId);
      if (srv.serviceId != 0) 
      {
        std::string label = srv.serviceLabel.utf8_label();
        PyObject* label_py = PyUnicode_FromString(label.c_str());
        return Py_NewRef(label_py);
      }
      else
        return Py_NewRef(Py_None);
    }

    virtual void onSNR(float snr) override
    { 
//      pool.enqueue([snr, this]
//      {
//        PyGILState_STATE gstate  = PyGILState_Ensure ();
//        PyObject *result = PyObject_CallMethod (python_impl, "onSNR", "(f)", snr);//
//
//        if (result)
//           Py_DECREF (result);
//        PyGILState_Release (gstate);
//      });
    }

    virtual void onFrequencyCorrectorChange(int fine, int coarse) override 
    { 
//      pool.enqueue([fine, coarse, this]
//      {
//        PyGILState_STATE gstate  = PyGILState_Ensure ();
//        PyObject *result = PyObject_CallMethod (python_impl, "onFrequencyCorrectorChange", "(ii)", fine, coarse);
//
//        if (result)
//           Py_DECREF (result);
//        PyGILState_Release (gstate);
//      });
    }

    virtual void onSyncChange(char isSync) override 
    { 
      pool.enqueue([isSync, this]
      {
        synced = isSync;
        PyGILState_STATE gstate  = PyGILState_Ensure ();
        PyObject *result = PyObject_CallMethod (python_impl, "onSyncChange", "(c)", isSync);

        if (result)
           Py_DECREF (result);
        PyGILState_Release (gstate);
      });
    }
    virtual void onSignalPresence(bool isSignal) override
    { 
//      pool.enqueue([isSignal, this]
//      {
//        PyGILState_STATE gstate  = PyGILState_Ensure ();
//        PyObject *result = PyObject_CallMethod (python_impl, "onSignalPresence", "(p)", isSignal);
//
//        if (result)
//           Py_DECREF (result);
//        PyGILState_Release (gstate);
//      });
    }

    virtual void onServiceDetected(uint32_t sId) override
    {
      pool.enqueue([sId, this]
      {
        PyGILState_STATE gstate  = PyGILState_Ensure ();
        PyObject *result = PyObject_CallMethod (python_impl, "onServiceDetected", "(k)", sId);

        if (result)
           Py_DECREF (result);
        PyGILState_Release (gstate);
      });
    }

    virtual void onNewEnsemble(uint16_t eId) override
    {
      pool.enqueue([eId, this]
      {
        PyGILState_STATE gstate  = PyGILState_Ensure ();
        PyObject *result = PyObject_CallMethod (python_impl, "onNewEnsemble", "(I)", eId);

        if (result)
           Py_DECREF (result);
        PyGILState_Release (gstate);
      });
    }

    virtual void onSetEnsembleLabel(DabLabel& label) override
    {
      pool.enqueue([label, this]
      {
        PyGILState_STATE gstate  = PyGILState_Ensure ();
        PyObject *result = PyObject_CallMethod (python_impl, "onSetEnsembleLabel", "(s)", label.utf8_label().c_str());

        if (result)
          Py_DECREF (result);
        PyGILState_Release (gstate);
      });
    }

    virtual void onDateTimeUpdate(const dab_date_time_t& dateTime) override
    {
//      pool.enqueue([dateTime, this]
//      {
//        struct tm dabtime;
//        dabtime.tm_year = dateTime.year - 1900;
//        dabtime.tm_mon  = dateTime.month - 1;
//        dabtime.tm_mday = dateTime.day;
//        dabtime.tm_hour = dateTime.hour + dateTime.hourOffset;
//        dabtime.tm_min  = dateTime.minutes + dateTime.minuteOffset;
//        dabtime.tm_sec  = dateTime.seconds;
//        time_t timestamp = mktime(&dabtime);
//
//        PyGILState_STATE gstate  = PyGILState_Ensure ();
//        PyObject *result = PyObject_CallMethod (python_impl, "onDateTimeUpdate", "(i)", timestamp);
//
//        if (result)
//           Py_DECREF (result);
//        PyGILState_Release (gstate);
//      });
    }

    virtual void onFIBDecodeSuccess(bool crcCheckOk, const uint8_t* fib) override 
    {
//      pool.enqueue([crcCheckOk, fib, this]
//      {
//        const uint16_t fiblarge = *fib;
//        PyGILState_STATE gstate  = PyGILState_Ensure ();
//        PyObject *result = PyObject_CallMethod (python_impl, "onFIBDecodeSuccess", "(pH)", crcCheckOk, &fiblarge);
//
//        if (result)
//           Py_DECREF (result);
//        PyGILState_Release (gstate);
//      });
    }
    
    virtual void onNewImpulseResponse(std::vector<float>&& /*data*/) override
    {
      /* Not yet implemented */
    }
    virtual void onNewNullSymbol(std::vector<DSPCOMPLEX>&& /*data*/) override
    { 
      /* Not yet implemented */
    }
    virtual void onConstellationPoints(std::vector<DSPCOMPLEX>&& /*data*/) override
    { 
      /* Not yet implemented */
    }

    virtual void onMessage(message_level_t level, const std::string& text, const std::string& text2 = std::string()) override
    {
//      pool.enqueue([level, text, text2, this]
//      {
//        bool isError = (level == message_level_t::Error);
//
//        PyGILState_STATE gstate  = PyGILState_Ensure ();
//        PyObject *result = PyObject_CallMethod (python_impl, "onMessage", "(ssp)", text, text2, isError);
//
//        if (result)
//           Py_DECREF (result);
//        PyGILState_Release (gstate);
//      });
    }

    virtual void onTIIMeasurement(tii_measurement_t&& m) override
    {
      /* Not yet implemented */
    }
};

PyObject *init_device (PyObject* /*self*/, PyObject *args)
{
  char* deviceName;
  int   gain;
  PyObject* pythonController;
  PyArg_ParseTuple (args, "Osi", &pythonController, &deviceName, &gain);
  PythonRadioController* ri = new PythonRadioController(pythonController, deviceName, gain);
  if (ri->device)
    return PyCapsule_New (ri, "library_object", NULL);
  else
    Py_RETURN_NONE;
}

PyObject *set_channel (PyObject */*self*/, PyObject *args) 
{
  PyObject  *handle_capsule;
  char  *chan;

  PyArg_ParseTuple (args, "Os", &handle_capsule, &chan);
  PythonRadioController* ri = reinterpret_cast<PythonRadioController*>(PyCapsule_GetPointer (handle_capsule, "library_object"));
  
  std::string channel(chan);
  bool chan_ok = ri->set_channel(channel);
  return chan_ok ? Py_NewRef(Py_True) : Py_NewRef(Py_False);
}

PyObject *subscribe_program (PyObject */*self*/, PyObject *args) 
{
  PyObject* programme_handler;
  PyObject* handle_capsule;
  uint32_t sId;

  PyArg_ParseTuple (args, "OOi", &handle_capsule, &programme_handler, &sId);
  PythonRadioController* ri = reinterpret_cast<PythonRadioController*>(PyCapsule_GetPointer (handle_capsule, "library_object"));

  bool subscribe_ok = ri->subscribe_program(programme_handler, sId);
  return subscribe_ok ? Py_NewRef(Py_True) : Py_NewRef(Py_False);
}

PyObject *get_service_name (PyObject */*self*/, PyObject *args)
{
  PyObject  *handle_capsule;
  uint32_t sId;

  PyArg_ParseTuple (args, "OI", &handle_capsule, &sId);
  PythonRadioController* ri = reinterpret_cast<PythonRadioController*>(PyCapsule_GetPointer (handle_capsule, "library_object"));

  return ri->get_service_name(sId);
}

PyObject *unsubscribe_program (PyObject */*self*/, PyObject *args) {
  PyObject  *handle_capsule;
  uint32_t sId;

  PyArg_ParseTuple (args, "OI", &handle_capsule, &sId);
  PythonRadioController* ri = reinterpret_cast<PythonRadioController*>(PyCapsule_GetPointer (handle_capsule, "library_object"));

  bool unsubscribe_ok = ri->unsubscribe_program(sId);
  return unsubscribe_ok ? Py_NewRef(Py_True) : Py_NewRef(Py_False);
}

PyObject *close_device (PyObject */*self*/, PyObject *args) {
  PyObject *handle_capsule;

  PyArg_ParseTuple (args, "O", &handle_capsule);
  PythonRadioController* ri = reinterpret_cast<PythonRadioController*>(PyCapsule_GetPointer (handle_capsule, "library_object"));

  ri->close_device();
  Py_RETURN_NONE;
}

PyObject *finalize (PyObject */*self*/, PyObject *args) {
  PyObject *handle_capsule;

  PyArg_ParseTuple (args, "O", &handle_capsule);
  PythonRadioController* ri = reinterpret_cast<PythonRadioController*>(PyCapsule_GetPointer (handle_capsule, "library_object"));

  delete ri;
  Py_RETURN_NONE;
}

static PyMethodDef module_methods [] = {
  {"init_device",          init_device,         METH_VARARGS, ""},
  {"set_channel",         set_channel,         METH_VARARGS, ""},
  {"subscribe_program",   subscribe_program,   METH_VARARGS, ""},
  {"unsubscribe_program",  unsubscribe_program, METH_VARARGS, ""},
  {"close_device",        close_device,        METH_VARARGS, ""},
  {"finalize",            finalize,            METH_VARARGS, ""},
  {"get_service_name",    get_service_name,    METH_VARARGS, ""},
  {NULL, NULL, 0, NULL}
};

static struct PyModuleDef welle_io = {
  PyModuleDef_HEAD_INIT,
  .m_name = "libwelle_py",
  .m_doc = "",
  .m_size = -1,
  module_methods,
  NULL,
  NULL,
  NULL,
  NULL
};

/*

static PyObject *
WPH_Test(PythonRadioController *self, PyObject *Py_UNUSED(ignored))
{
  std::cout << "In WPH_Test in C" << std::endl;
  Py_RETURN_NONE;
}

static PyMethodDef wph_methods[] = 
{
  {"WPH_Test", (PyCFunction) WPH_Test, METH_NOARGS, "Return the name, combining the first and last name"
  },
  {NULL}  // Sentinel 
};

typedef struct {
    PyObject_HEAD
    PythonRadioController* wph;
} rc_wrapper;

static PyTypeObject RadioControllerType = 
{
  PyVarObject_HEAD_INIT(NULL, 0)
  .tp_name = "libwelle_py.RadioController",
  .tp_basicsize = sizeof(rc_wrapper),
//  .tp_dealloc = (destructor) Custom_dealloc,
  .tp_itemsize = 0,
  .tp_flags = Py_TPFLAGS_DEFAULT,
  .tp_doc = PyDoc_STR("Custom objects"),
  .tp_methods = wph_methods,
//  .tp_members = Custom_members,
//  .tp_init = (initproc) Custom_init,
  .tp_new = PyType_GenericNew,
};
*/
PyMODINIT_FUNC
PyInit_libwelle_py (void) {
  PyObject *m;
//  if (PyType_Ready(&RadioControllerType) < 0)
//    return NULL;

  m = PyModule_Create(&welle_io);
  if (m == NULL)
    return NULL;
	
//  Py_INCREF(&RadioControllerType);
//  if (PyModule_AddObject(m, "RadioController", (PyObject *) &RadioControllerType) < 0) 
//  {
//    Py_DECREF(&RadioControllerType);
//    Py_DECREF(m);
//    return NULL;
//  }

  return m;
}
