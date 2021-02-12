
#include "Plugin.h"

namespace plugin { namespace @PACKAGE_NS_UNDERSCORE@@PACKAGE_NAME@ { Plugin plugin; } }

using namespace plugin::@PACKAGE_NS_UNDERSCORE@@PACKAGE_NAME@;

zeek::plugin::Configuration Plugin::Configure()
	{
	zeek::plugin::Configuration config;
	config.name = "@PACKAGE_NS_COLONS@@PACKAGE_NAME@";
	config.description = "TODO: Insert description";
	config.version.major = 0;
	config.version.minor = 1;
	config.version.patch = 0;
	return config;
	}
