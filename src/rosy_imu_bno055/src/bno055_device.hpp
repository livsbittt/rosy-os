#pragma once
#include <array>
#include <cstdint>
#include <functional>
#include <string>

namespace rosy_imu
{
class Device {
public:
  using Log = std::function<void(const std::string &)>;
  Device(std::string interface, Log log, std::function<bool()> running);
  ~Device();
  Device(const Device &) = delete;
  Device & operator=(const Device &) = delete;
  void initialize(bool reset_on_start = false);
  std::array<uint8_t, 32> read();

private:
  void write_register(int reg, int value, const char *stage);
  void wait_register(int reg, int expected, const char *stage, int timeout_ms);
  int fd_ = -1;
  std::string interface_;
  Log log_;
  std::function<bool()> running_;
};
}
