#include "config.h"
#include "Plugin.h"

namespace plugin { namespace @PACKAGE_NS_UNDERSCORE@@PACKAGE_NAME@ { Plugin plugin; } }

using namespace plugin::@PACKAGE_NS_UNDERSCORE@@PACKAGE_NAME@;

zeek::plugin::Configuration Plugin::Configure()
	{
	zeek::plugin::Configuration config;
	config.name = "@PACKAGE_NS@::@PACKAGE_NAME@";
	config.description = "TODO: Insert description";
	config.version.major = PACKAGE_VERSION_MAJOR;
	config.version.minor = PACKAGE_VERSION_MINOR;
	config.version.patch = PACKAGE_VERSION_PATCH;
	return config;
	}
