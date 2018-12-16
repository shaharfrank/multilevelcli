# Multi Level CLI

This module supports command line parsing of complex (multi-command) and nested (multi-level) CLIs such as the
"Cisco" CLI or the GCP _gcloud_ cli. 

The main features multilevelcli provides are:
* support for multiple commands
* command grouping
* nested groups
* automatic tree generation
* level aware options parsing
* array(list) and struct(dict) arguments and options
* nested arguments and options types support and parsing

# Comparison to argparse module
**multilevelcli** is not compatible with and not exactly a superset of argparse. It is not designed as an
argparse substitute in the general case. It is meant to be used for complex CLI cases where the standard 
argparse is hard to use and lacking functionality. For most applications
 the cmdline parsing may be easier with argparse. In fact **multilevelcli** doesn't support single command CLIs.

Still there are some areas where **multilevelcli** may be generally better:
* It is simpler to use programmatically - i.e. to generate CLI from some other structured definition language such
as Swagger.
* In most cases there is no need for nested parsers as the parser is multilevel by design
* The help generation and invocation is simpler
* The typing system is simpler and more powerful in most cases
* It is possible to do the parsing in stages, i.e. multiple times

The following argparse features are not supported (probably a partial list):
* dynamic arguments number (as in add_argument(**narg**=...))
* **actions** (but they are not needed in most cases)
* special **types** such as 'open'
* **choices**
* **required** options (as having a 'required' option is a little bit odd, isn't it?)
* **metavar** (multilevelcli uses the arg type)
* **dest** (multilevelcli always uses the arg name)

# The general model of operation
Basically the multilevelcli follows the argparse model. A parser needs to be defined, and all of the groups,
commands, arguments and options must be defined before you start the parsing.
After the parser is called, a namespace object is returned. The namespace object is similar
in principle to the argparse namespace object, but is much more powerful as it supports levels, groups
and nested types.  

# Multilevelcli entities

## Parser
The parser is the main class. You must create at least one MultiLevelArgParse instance and specify a name for it.
For example:

```python
    cli = multilevelcli.MultiLevelArgParse("testcli1")
```
    
## Command
The entire pupose of the CLI is to let the user issue commands with parameters and/or options. Any flow
that doesn't end up with a parsable command is an unfinished flow and by default the help usage will be shown
to guide the user to add the missing parts. This behavior can be changed (see default handling below).
Use the **add_command()** method to add a cli command. Any number of commands may be added on each level.
Each command may have (mandatory) positional arguments and optional nonpositional options (see below).
A command needs at least a name (level unique). The description is optional
but of course highly desirable if meaningful help/usage screens are required.
The add_command() function returns
a command object. Store that object if you need to add options or arguments to it.
For example:

```python
    cli.add_command("version")
    list_cmd = cli.add_command("list", description="list all entities")
```
    
## Argument
Use the **add_argument()** to add a positional argument to a command (object). The arguments order is determined
by the creation order. All arguments are mandatory. 
A (command scope unique) name must be provided for each argument and is used to retrieve the argument value.
An optional description can be provided as well as 
argtype (see the _types_ section below). The default argtype is 'str'.

```python
    list_cmd.add_argument("name", description="The name of the item to be listed")
```

## Option
Use the **add_option()** to add optional, non positional parameters to groups and/or commands.
Options are level aware and must be uniquely named within the level or command. Short and long options
are supported, and at least one of them must be defined.
A description is optional. If no opttype is provided the option is boolean (i.e. a flag option).
An option type can be of any supported type (see the _types_ section below).
For example:

```python
    cli.add_option('q', 'quiet', description="do not emit messages") # root (group) level option.  short (-q) and long (--quiet)
    list_cmd.add_option(None, 'id', description="id of the listed object") # command level option (only long - i.e., --id)
```
    
## Group
Group is used to create a new level of commands. In most cases it aggregates commands on a specific object or topic.
For example the gcp cli **gcloud** has a _compute_ group that aggregates 'images', 'instances', 'ssh', etc.
The cli parser object is the root group, and level 1 groups are attached to it.
Group levels are generated via nesting.
On each level, groups and commands may be used together. The resulting group object needs to
be stored so that you can add options, groups and/or commands to it.
For example:

```python
    compute = cli.add_group("compute")
    instances = compute.add_group("instances")
    instances.add_command("list")
    instances.add_command("new")
```

## CliResult 
CliResult is the object returned at runtime by the cli parser's `cli.parse()` method. It contains the parsing results
and the final values of the selected command, the command parameters and the options. Separate namespaces
(see below) are maintained for each level.
The most significant methods are:
- .**command_name**() - returns the command name (str) selected by the user
- .**args**() - returns the selected command arguments namespace. Each argument is a key, and the parsed user input is
its value. 
- .**opt**() - returns the selected command options namespace. Options apper in this namespace if set by user and/or they
have a default value.
- .**ns**() - Return a global namespace containing all options and arguments gathered
from all levels. The options and argument keys are set in full path format where the group and command(s)
are added to the name
and seperated by a dot. So, for example, if you have a command "vms instances new <id>" the id argument key in the namespace
will be "vms.instances.new.name".
- .**command**() - returns the command _object_ matching the user's input
- .**group**() - returns the group _object_ to which the command belongs
- .**unparsed_tokens**() - return the tokens that were not parsed. This is required  during partial parsing.
- .**command_ctx**() - get the user defined command context (see below)

## Namespace
A namespace is a python dictionary with some convenience function to allow accessing the dictionary keys
as members, and nested names lookup are supported too (e.g. you can lookup 'vms.instances.new.name' ). So instead of
using the standard python dict lookup _a["key"]_ you can do just _a.key_.

## Command tree generation
A complete command tree listing all groups and the commands in each group can be printed
by calling the `cli.show_tree()` method. There is no default binding
to this function, and the program must explicitly call this function as an implementation of a command
or option.
An example of such output:

    [./clitest2.py]    - testcli2
        tree 
        [vms]    
            [instances]    - commands on vm instances
                list - list instances
        [networks]    
            list - list networks

## Default command handling
If no command is found the default function is triggered. By default it is set to show the usage and exit, but
this can be changed by setting **defaultfn** or by passing a defaultfn argument during the group and/or command
initialization and or the parser. A default fn is a function that accepts a
single _MultiLevelCliBase.GroupType_ argument.
Several predefined utility functions exist, for example _usage_and_raise_no_command_ that raises a NoCommand
exception instead of exiting (so that the program can trap and handle it).
For example:

```python
    # root level default handling
    cli = MultiLevelArgParse("demo cli", defaultfn=usage_and_raise_no_command, help=usage_and_raise_help)
    # 'class' group default
    class_group = cli.add_group("class", defaultfn=usage_and_raise_no_command)

    try:
        parsed_input = cli.parse()
    except NoCommand:
        print("No command was entered.  Valid commands:")
        cli.show_tree()
```

## Help generation
By default the options '-h' and '--help' call the default help function **defhelpfn** that is set to _usage_and_exit_.
To change this you can change the defhelpfn variable and/or pass the help argument during group/command
initializtion. A help function is a function that accepts a single _MultiLevelCliBase.ParseBase_ argument.
Setting the help function to None disables the default help handling.
For example:

```python
    # group level help override
    alpha_group = cli.add_group("alpha", help=usage_help_and_raise_nocommand)
    # command level help override
    cmd = alpha_group.add_command("list", help=usage_help_and_raise_nocommand)
```

## Command user context
A user context can be set during command initialization. This context is returned via the
namespace in the CliResult (see above). A different context can be set for each command. This is especially useful for automatic cli generation **[TODO: explain how]**. For example:
```python

    beta_group.add_command("test", ctx="context")
    ...
    ctx = cli.parse().command_ctx()
```

## Partial parsing
To allow the parser to parse only tokens it is programmed to and ignore the rest just initialize the cli with
the partial flag. After parsing you can retrieve the unparsed tokens using the CliResult.unparsed_tokens() method **[TODO: explain format of the result. Is this a string? list? dictionary?]**.
For example:
```python

    result = cli.parse(partial=True)
    tokens = result.unparsed_tokens()
    ...
    # do what you need here. 
```

## Arguments and Options types
Arguments and option values can be of any type. The main restriction is that the type must support simple (i.e.
parameterized) cast from simple text (str) format. This means that most native python simple types are supported
such as 'str', 'int', 'double', 'float', etc.
For example:
```python
        test_cmd = cli.add_command("user")
        test_cmd.add_argument('name', argtype=str)  # str is the default
        test_cmd.add_argument('age', argtype=int, description="in years")
        test_cmd.add_argument('weight', argtype=float, description="in KG")
        test_cmd.add_option('m', 'married')     # default boolean/flag option
        test_cmd.add_option(None, 'spouse', opttype=str)    # string value for option
```
```
        # from clitest2.py - a sample input:        
        $ ./clitest2.py user Jack 28 72.8 -m --spouse Maria
```

**[TODO: for simplicity, why not rename 'argtype' and 'opttype' to 'type'?]**

In addition compound values are supported through Arrays(lists) and
structures (dictionaries).
Arrays are variable size lists of the same type and are denoted by '[' <type> ']'. For example an array of int
variables is defined as [ int ].
Structures are dictionaries of keys and values. Keys are strings, and the value can be of any type. For example a
structure describing a person's name and age may be defined as ' { name : str, age : int } '.

Examples (from clitest2.py):
```python

        child_cmd = cli.add_command("children", description="add children using array parameters and options")
        child_cmd.add_argument("number", argtype=int, description="number of children")
        child_cmd.add_argument("ages", argtype=[int], description="list of children ages")   # array of int example
        child_cmd.add_option("names", opttype=[str], description="list of children names")   # array of str example

        user_cmd = cli.add_command("person", description="add a person using a struct parameter")
        user_cmd.add_argument('record', argtype={ "name": str, "age" : int}, description="a person record")  # struct example
```
```
        $ ./clitest2.py children 2 [ 5, 11 ]
        children is added. 
	        {'number': 2, 'ages': [5, 11]}

        $ ./clitest2.py person { name = joe, age = 27 }
        person is added. 
	        {'record': {'name': 'joe', 'age': 27}}
```

## Nested types
Types may be nested. For example
```python
        family_cmd = cli.add_command("family", description="add a family using a compound parameter")
        p = family_cmd.add_argument('members', argtype=[{ "name": str, "age" : int,
                                                        "children" : [ { "name" : str, "age" : int}] }],
                                  description="member records")  # array of struct example
```
```        
        $ ./clitest2.py family [{ name = Sara, age = 34 }, {name = Joe, age=33, children = [{name = Mike, age=3}, {name = Dana, age=7}] }]
        family has been added:
	        {'members': [{'name': 'Sara', 'age': 34}, {'name': 'Joe', 'age': 33, 'children': [{'name': 'Mike', 'age': 3}, {'name': 'Dana', 'age': 7}]}]}
```

# Examples
## Example 1: A single command example:
```python
#!/usr/bin/env python3

import multilevelcli

if __name__ == "__main__":
    cli = multilevelcli.MultiLevelArgParse("testcli1")
    cli.add_option("t", "treelevels", opttype=int, default=7, description="max tree levels to process")
    cli.add_option("q", "quiet", description="do not emit messages")
    cli.add_command("list")

    ns = cli.parse()

    print ("### Success! namespace='%s'" % str(ns))
```

### Exampel 1 usage
An automatic help/usage is generated and emmited if no command is found.
The help screen can be shown by using the automatic -h/--help option.

    $ ./clitest1.py 
    Usage: ./clitest1.py  [-h/--help] [-t/--treelevels <int>] [-q/--quiet] list
    
    Description:
        testcli1
    
    Options:
        -h/--help                    - help screen (this screen)
        -q/--quiet                   - do not emit messages
        -t/--treelevels       <int>  - max tree levels to process. Default '7'
    
    Sub Commands:
        list

### Example 2 (based on testcli2.py):
```python
#!/usr/bin/env python3

import multilevelcli
import sys

if __name__ == "__main__":
    try:
        cli = multilevelcli.MultiLevelArgParse("testcli2")
        assert isinstance(cli, multilevelcli.MultiLevelArgParse)
        cli.add_option("t", "treelevels", opttype=int, default=7, description="max tree levels to process")
        cli.add_option("q", "quiet", description="do not emit messages")
        vms = cli.add_group("vms")
        networks = cli.add_group("networks")
        list_net_cmd = networks.add_command("list", description="list networks")

        cli.add_command("tree", description="show command tree")
        cli.add_command("syntax", description="show command line syntax")

        instances = vms.add_group("instances", description="commands on vm instances")
        list_cmd = instances.add_command("list", description="list instances")
        list_cmd.add_option("l", "long", description="use long listing")

        user_cmd = cli.add_command("user", description="add user using parameters")
        user_cmd.add_argument('name', argtype=str)  # str is the default
        user_cmd.add_argument('age', argtype=int, description="in years")
        user_cmd.add_argument('weight', argtype=float, description="in KG")
        user_cmd.add_option('m', 'married')     # default boolean/flag option
        user_cmd.add_option(None, 'spouse', opttype=str)    # string value for option


        child_cmd = cli.add_command("children", description="add children using array parameters and options")
        child_cmd.add_argument("number", argtype=int, description="number of children")
        child_cmd.add_argument("ages", argtype=[int], description="age list of children")   # array of int example
        child_cmd.add_option("names", opttype=[str], description="name list of children")   # array of str example

        person_cmd = cli.add_command("person", description="add a person using a struct parameter")
        person_cmd.add_argument('record', argtype={ "name": str, "age" : int}, description="a person record")  # struct example

        family_cmd = cli.add_command("family", description="add a famility using a compound parameter")
        p = family_cmd.add_argument('members', argtype=[{ "name": str, "age" : int,
                                                        "children" : [ { "name" : str, "age" : int}] }],
                                  description="member records")  # array of struct example
        ########
        ns = cli.parse()

        command =  str(ns.command())

        if command == "tree":
            cli.show_tree()
        elif command == "syntax":
            cli.show_systax()
        elif command in ["user", "person", "children"]:
            if not ns.quiet:
                print("%s is added. \n\t%s\n" % (command, ns.args()))
        elif command == 'family':
            if not ns.quiet:
                for m in ns.members:
                    print("Adding family member %s age %d" % (m['name'], m['age']))
                    if not "children" in m:
                        continue
                    for c in m["children"]:
                        print("\tChildren %s age %d" % (c['name'], c['age']))
        # other commands...

    except Exception as e:
        print("Error: " + str(e))
        sys.exit(1)

    print ("\n### Success! namespace='%s'" % str(ns))
    print ("ns: %s" % ns.ns())
    print ("group: %s" % ns.group())
    print ("command: '%s'" % ns.command())
    print ("args: %s" % ns.args())
    print ("opt: %s" % ns.opt())
```
