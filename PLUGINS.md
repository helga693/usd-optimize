# Writing Plugins

This document provides a brief description of authoring a Usd Optimize plugin. It assumes you have usd optimize as a dependency and it is linked and the includes are available.

## Basic Implementation

Implementing a plugin is straightforward. Define a new class derived from `usd_optimize::Operation`. The following snippet lists the required abstract functions you must implement.

```c++
#include <usd_optimize/core/Operation.h>

class MyPlugin : public usd_optimize::Operation
{
 public:
    // Return your name/contact so people can get in touch if necessary
    std::string getAuthor() const override;

    // Return the version of your plugin
    UsdOptimizePluginVersion getVersion() const override;

    // Return the category of your plugin used for reporting
    std::string getCategory() const override;

    // Return the UI submenu group (e.g. "Geometry", "Materials", "Stage", "Utilities")
    std::string getDisplayGroup() const override;

 protected:
    // This is the function that is called when a user runs your plugin
    OperationResult executeImpl() override;

};
```

You then implement the plugin class. You must call the base Operation constructor with a key/name, a display name, and a readable description. The display name and description will be used in the user interface to help users understand what your plugin does. You then implement the `executeImpl()` function to actually run your logic when someone executes your plugin.

```c++

// Provide a key for your plugin, a display name, and a description
MyPlugin::MyPlugin()
    : Operation("myPlugin", "My Plugin", "A test plugin that does awesome things")
{
}

// In case users have questions/suggestions/bug reports/etc
std::string MyPlugin::getAuthor() const
{
    return "Your Name";
}

UsdOptimizePluginVersion MyPlugin::getVersion() const
{
    // major / minor / rev
    return { 1, 0, 0 };
}

std::string MyPlugin::getCategory() const
{
    return "MyOperation";
}

std::string MyPlugin::getDisplayGroup() const
{
    return s_displayGroupGeometry; // or s_displayGroupMaterials, s_displayGroupStage, s_displayGroupUtilities
}

OperationResult MyPlugin::executeImpl()
{
    // Your actual plugin logic goes here
    for (const auto& prim : getUsdStage()->Traverse())
    {
        ...
    }

    return { true };
}
```

`OperationResult` is a struct, not an enum (see `usd_optimize/core/Defs.h`): `{ true }` reports success, and `{ false, getCStr(error) }` reports a failure with a message.

The `getDisplayGroup()` function determines which submenu your operation appears under in the Usd Optimize UI. The available constants are `s_displayGroupGeometry`, `s_displayGroupMaterials`, `s_displayGroupStage`, and `s_displayGroupUtilities`. If not overridden, the operation will appear at the top level of the menu.

There are some useful functions available on the base operation class such as `getUsdStage()`, to get the USD stage that is being processed, and various logging functions that can propagate logs to the user interface. See `usd_optimize/core/Operation.h` for more information.

## Arguments

The main other thing you'll want to do is define the arguments you support, which happens in your plugin constructor. This is the one place you need to define arguments - from here they will be available in the user interface, via JSON configuration files that can run Usd Optimize operations, and in the command-line interface. As such when adding an argument there are a number of things you must provide.

Each argument requires a key, a display name, a display type and a description. They also point at a member variable. This variable will be set with the value a user has chosen before `executeImpl()` is called on your plugin.


```c++
MyPlugin::MyPlugin()
    : Operation("myPlugin", "My Plugin", "A test plugin that does awesome things")
{
    addArgument("myBoolSetting",
                "Bool Setting",
                kDisplayTypeBool,
                "This will show a checkbox in the UI",
                m_myBool);
}
```

### Default Values

The default value of an argument (used whenever a user does not explicitly specify a value for it) is read from the member variable at the time you call `addArgument`. Ensure it has the appropriate default value before doing so. All arguments are optional, so a sensible default should be specified.

### Argument Types

Arguments can essentially be types that are supported by JSON, which is used internally.
The basic data types are supported (bool, int, float, double, string) and also arrays, based on vector member variables. Arrays of the same basic types are supported, but arrays cannot have mixed types. You define them the same way you would define any other argument:

```c++
// Assuming a member variable on your class somewhere
std::vector<std::string> m_paths;

// In the plugin constructor
addArgument("paths",
            "Prim Paths",
            kDisplayTypePrimPaths,
            "Optional prim filter",
            m_paths);
```

### Display Types

Arguments have "Display Types". These are hints to the User Interface on how to display an argument. For example, you can use `kDisplayTypeFloat` to have a text entry box to type in a float. You can also use `kDisplayTypeFloatSlider`, along with an optional min/max, to instead use a draggable float widget. Most are simple, but there are some more specialised ones - for example `kDisplayTypePrimPaths` provides a way to add prims based on stage selection, drag/drop, or via a popup window.

The full list of display types defined in `usd_optimize/core/Argument.h`:

| Constant | Description |
|---|---|
| `kDisplayTypeAttributeList` | A list of attribute names |
| `kDisplayTypeBool` | A checkbox |
| `kDisplayTypeCode` | A code editor (e.g. for Python scripts) |
| `kDisplayTypeEnum` | A drop-down combo box |
| `kDisplayTypeFloat` | A float text entry |
| `kDisplayTypeFloatArray` | An array of floats |
| `kDisplayTypeFloatPresets` | A float with named presets |
| `kDisplayTypeFloatSlider` | A draggable float slider |
| `kDisplayTypeInt` | An integer text entry |
| `kDisplayTypeIntSlider` | A draggable integer slider |
| `kDisplayTypePrimPath` | A single prim path |
| `kDisplayTypePrimPaths` | A list of prim paths with selection/drag-drop support |
| `kDisplayTypeText` | A text entry |
| `kDisplayTypeTextList` | A list of text entries |


### Enum Arguments

You can create arguments that result in an enum in your plugin. You must specify any of the enum options that you would like to expose. The order you list them will be respected in the UI, and you are not required to provide every option - only the ones you want users to be able to choose between.

```c++

    enum class MyEnumType
    {
        eFoo = 0,
        eBar = 1,
        eBaz = 2,
    };

    ...

    addArgument("myEnum", "My Enum", kDisplayTypeEnum, "An enum option", m_myEnum)
        .setEnumValues<MyEnumType>({
            { MyEnumType::eFoo, "Foo" },
            { MyEnumType::eBar, "Bar" },
        });
```

This will create a drop-down combo box in the user interface with the options "Foo" and "Bar". At execution time, `m_myEnum` will be populated with the corresopnding enum.

### Further Argument Configuration

As in the enum example above, calling `addArgument` will return a reference to the argument and then further functions can be called on it to provide extra configuration. For example, you may want to define a float argument with a min/max, and also hide it from the User Interface:

```c++
    addArgument("myFloat",
                "A Float Value",
                kDisplayTypeFloat,
                "This argument is not exposed in the UI",
                m_myFloat)
        .setVisible(false)
        .setMin(0.0)
        .setMax(1.0);
```

Note that hidden arguments will still be displayed in the Command Line Interface, so these are useful for debug.  They are also respected via JSON configuration files.

The following configuration methods are available on arguments (all return a reference for chaining):

| Method | Description |
|---|---|
| `setMin(float)` | Set a minimum value |
| `setMax(float)` | Set a maximum value |
| `setStep(float)` | Set a step value for UI sliders |
| `setPrecision(int)` | Number of digits of precision for the UI to display |
| `setVisible(bool)` | Hide the argument from the UI |
| `setPlaceholder(string)` | Placeholder text shown in empty UI widgets |
| `setEnableIf(string)` | A python expression that controls whether the UI widget is enabled based on other argument values |
| `setVisibleIf(string)` | A python expression that controls whether the argument is visible based on other argument values |
| `setEnumValues<T>(vector)` | Map enum values to display names for combo boxes |
| `setFloatPresets(vector)` | Map float values to named presets |

See `usd_optimize/core/Argument.h` for more.

### Grouping Arguments

Arguments can be organized into logical groups using `addGroup()`. Groups can have their own conditional visibility/enable expressions, which is more convenient than specifying them per argument.

```c++
addGroup("myGroup",
         addArgument("argA", ...),
         addArgument("argB", ...)
).setVisibleIf("someOtherArg == 1");
```

For placing multiple argument widgets on the same UI row, use `addJoin()`:

```c++
addJoin(
    "Thresholds",
    "CPU and GPU vertex count thresholds",
    addArgument("cpuThreshold", "CPU Threshold", kDisplayTypeIntSlider, "CPU threshold", m_cpu).setMin(0),
    addArgument("gpuThreshold", "GPU Threshold", kDisplayTypeIntSlider, "GPU threshold", m_gpu).setMin(0));
```

## Analysis Mode

Operations can optionally support an analysis mode, which allows them to inspect the stage and report findings without making any modifications. This is used by the Performance Validators integration to expose Usd Optimize analysis through usd-validation-nvidia.

To support analysis, override `getSupportsAnalysis()` to return `true` and implement `executeAnalysisImpl()`:

```c++
class MyPlugin : public usd_optimize::Operation
{
public:
    bool getSupportsAnalysis() const override { return true; }

protected:
    OperationResult executeImpl() override;
    OperationResult executeAnalysisImpl() override;
};
```

When running in analysis mode, `executeAnalysisImpl()` will be called instead of `executeImpl()`. Use the report object (via `getReport()`) to record findings.

## Registering your plugin

Plugins must be registered with the Usd Optimize in order for them to be found and used.  For plugins contained within the Usd Optimize repository there is a convenience macro provided to register your plugin.  So long as it is built to the default `operations` folder, then all that is required is to specify this in your .cpp file and the plugin will be found and registered automatically:

```c++
// Register plugin
USD_OPTIMIZE_PLUGIN_INIT(usd_optimize::MyPlugin);
```
If you are authoring a plugin outside of the Usd Optimize there are two options to register your plugin:

Set the `USD_OPTIMIZE_PLUGIN_PATH` environment variable to include a path to the directory that contains your plugin(s). The paths in this variable are delimited using the `;` character on Windows systems and `:` on all other systems.

Otherwise you can register your plugin from code. In your startup code, instantiate your plugin and then register it along with an unload callback. This will be called if the plugin is unloaded so you can tidy up.

```c++
#include <usd_optimize/core/Core.h>

// Create an instance of your plugin somewhere
static MyPlugin* s_myPlugin = nullptr;

// Whatever unload you want to do
static void myPluginUnload()
{
    delete s_myPlugin;
    s_myPlugin = nullptr;
}

// Inside your plugin startup code, register MyOperation with usd optimize.
s_myPlugin = new MyPlugin();
auto& core = usd_optimize::UsdOptimizeCore::getInstance();
core.registerOperation( &usdOptimizeOperationCreate<MyOperation>, &usdOptimizeOperationDelete<MyOperation> );
```

## Execution

An instance of your class is registered as a plugin. When a user executes your plugin it will be populated with whatever argument values they have specified. Your `executeImpl()` function is then called. Your plugin may be executed multiple times by a user, so after execution completes all arguments (their member variables) will be reset to their default values ready to be run again with whatever new configuration they have specified.

If you maintain any other state on your plugin class then you can tidy this up at the beginning or end of your `executeImpl()` function if necessary.


## Documenting Plugins

Override `getDocumentation()` to return reStructuredText describing what the operation does and how to tune it. The per-operation page `docs/operations/<key>.rst` and the `docs/operations.rst` catalog are generated from that string plus your `addArgument()` declarations, by running `./repo.sh docs_gen --autogen_only` (`repo.bat` on Windows). Do not hand-edit the generated `.rst` files; they are marked AUTO GENERATED and your changes will be overwritten.
