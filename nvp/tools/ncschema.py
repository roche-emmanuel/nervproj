import netCDF4
import numpy as np

from nvp.nvp_object import NVPObject


class NCSchema(NVPObject):
    """Helper class used to parse the complete structure of a netcdf file"""

    def __init__(self, filename):
        """Constructor

        filename: name of the netcdf file to parse:
        """

        self.dimensions = {}
        self.grp_stack = []
        self.grp_attribs = {}
        self.variables = {}

        with netCDF4.Dataset(filename, "r") as dset:
            self.parse_dimensions(dset)
            self.parse_attribs(dset)
            self.parse_variables(dset)
            self.parse_groups(dset)

    def parse_dimensions(self, obj):
        """Parse the dimensions in an element"""

        if hasattr(obj, "dimensions"):
            prefix = "/".join(self.grp_stack)

            for dim_name, dim in obj.dimensions.items():
                if dim_name in self.dimensions:
                    raise ValueError(f"Dimension {dim_name} already registered")
                self.dimensions[dim_name] = [len(dim), prefix]

    def parse_groups(self, obj):
        """Parse the groups contained in an element"""

        for group_name, group in obj.groups.items():

            # Push this group name on the stack:
            self.grp_stack.append(group_name)

            self.parse_dimensions(group)
            self.parse_attribs(group)
            self.parse_variables(group)
            self.parse_groups(group)

            # Pop the group name:
            self.grp_stack.pop()

    def parse_attribs(self, obj, var_desc=None):
        """Parse attribs either for the current group
        if var_desc is None, otherwise for that target variable"""

        attribs = {}
        for attr_name in obj.ncattrs():
            attribs[attr_name] = getattr(obj, attr_name)

        if len(attribs) == 0:
            return

        prefix = "/".join(self.grp_stack) if len(self.grp_stack) > 0 else "root"

        if var_desc is None:
            # Register group attribs:
            self.grp_attribs[prefix] = attribs
            return

        var_desc["attribs"] = attribs

    def parse_variables(self, obj):
        """Parse variables"""

        prefix = "/".join(self.grp_stack)

        for var_name, var in obj.variables.items():

            desc = {
                "prefix": prefix,
                "var_name": var_name,
                "data_type": f"{var.dtype}",
                "dims": var.dimensions,
            }
            self.parse_attribs(var, desc)

            key = f"{prefix}/{var_name}"
            self.variables[key] = desc

    def get_shape(self, dims):
        """Get the shape tuple corresponding to a given list of dimensions"""

        return (self.dimensions[k][0] for k in dims)

    def convert_numpy_to_python(self, obj):
        """Convert from numpy to simple python elements."""
        if isinstance(obj, np.generic):
            return obj.item()
        elif isinstance(obj, (list, tuple)):
            return [self.convert_numpy_to_python(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: self.convert_numpy_to_python(value) for key, value in obj.items()}
        else:
            return obj

    def write_yaml_file(self, filename):
        """Write this schema as a yaml file"""

        desc = {
            "dimensions": self.dimensions,
            "grp_attribs": self.grp_attribs,
            "variables": self.variables,
        }

        desc = self.convert_numpy_to_python(desc)
        self.write_yaml(desc, filename)
