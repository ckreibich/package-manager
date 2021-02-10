#pragma once

#include <zeek/plugin/Plugin.h>

namespace plugin {
namespace @PACKAGE_NAMESPACE@_@PACKAGE_NAME@ {

class Plugin : public zeek::plugin::Plugin
{
protected:
	// Overridden from zeek::plugin::Plugin.
	zeek::plugin::Configuration Configure() override;
};

extern Plugin plugin;

}
}
