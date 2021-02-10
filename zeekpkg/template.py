"""
A module for instantiating different types of Zeek packages.
"""

class PackageTemplate():
    """
    Base class for all supported zkg package types.
    """
    def __init__(self):
        self._overlays = []

    def populate(self, package_info):
        pass

    def add_overlay(self, overlay):
        self._overlays.append(overlay)

    def instantiate(self, output_dir):
        pass

class PackageOverlay():
    pass

class PluginOverlay(PackageOverlay):
    pass

class SpicyOverlay(PackageOverlay):
    pass
