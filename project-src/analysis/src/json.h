//===- json.h - minimal JSON output ---------------------------------------===//
//
// Just enough to emit the analysis results. The module under analysis is
// untrusted input -- its identifiers, file paths and source text all end up in
// this output and then in an LLM prompt -- so nothing is ever emitted raw.
//
//===----------------------------------------------------------------------===//
#pragma once

#include <cstdio>
#include <string>

namespace irqrace {

inline std::string esc(const std::string &s) {
  std::string out;
  out.reserve(s.size() + 8);
  for (char c : s) {
    switch (c) {
    case '"':  out += "\\\""; break;
    case '\\': out += "\\\\"; break;
    case '\n': out += "\\n";  break;
    case '\r': out += "\\r";  break;
    case '\t': out += "\\t";  break;
    default:
      if (static_cast<unsigned char>(c) < 0x20) {
        char buf[8];
        snprintf(buf, sizeof buf, "\\u%04x", c);
        out += buf;
      } else {
        out += c;
      }
    }
  }
  return out;
}

inline std::string q(const std::string &s) { return "\"" + esc(s) + "\""; }

} // namespace irqrace
