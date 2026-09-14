# SPDX-FileCopyrightText: Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#


import base64

from usd_optimize.core.operation import Operation


class PythonScriptOperation(Operation):
    def __init__(self):
        super().__init__(
            "pythonScript",
            "Python Script",
            "Execute a user defined python script with access to the current USD stage.",
        )
        self.add_argument(
            "python",
            "Python Script",
            Operation.ArgumentDisplayTypeCode,
            "The Python script to execute.",
            # The "python" value is base64-encoded (execute() decodes it), so the default must be
            # encoded too -- a plaintext default fails b64decode and makes the shipped default
            # unusable. Encode inline so the actual default script stays readable here.
            base64.b64encode(b'print("Hello world!")').decode("ascii"),
        )

    @property
    def documentation(self):
        return (
            "This operation executes user defined python code with access "
            "to the current stage. It can be used to manipulate the stage "
            "in ways not currently supported by Usd Optimize. The "
            "python script can be stored in the Preset configuration file, "
            "making it reusable and portable."
        )

    @property
    def author(self):
        return "Usd Optimize (Internal)"

    @property
    def version(self):
        return (1, 0, 0)

    def execute(self, args):
        # decode the python code from the arguments
        base64_value = args["python"]
        base64_bytes = base64_value.encode("ascii")
        readable_bytes = base64.b64decode(base64_bytes)
        readable_value = readable_bytes.decode("ascii")
        # execute the python code
        _locals = {"stage": self.get_usd_stage()}
        env = dict(_locals, **globals())
        exec(readable_value, env, env)
        return True


#####################################
# Register Usd Optimize Plugin
#####################################


def usdOptimizePluginInit():
    return PythonScriptOperation()
