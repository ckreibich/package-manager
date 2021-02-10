
#include "Plugin.h"

namespace plugin { namespace @PACKAGE_NAMESPACE@_@PACKAGE_NAME@ { Plugin plugin; } }

using namespace plugin::@PACKAGE_NAMESPACE@_@PACKAGE_NAME@;

zeek::plugin::Configuration Plugin::Configure()
	{
	zeek::plugin::Configuration config;
	config.name = "@PACKAGE_NAMESPACE@::@PACKAGE_NAME@";
	config.description = "TODO: Insert description";
	config.version.major = 0;
	config.version.minor = 1;
	config.version.patch = 0;
	return config;
	}
