#!/usr/bin/env python3

import multilevelcli
import traceback
import sys

if __name__ == "__main__":
    try:
        cli = multilevelcli.MultiLevelArgParse("testcli1")
        assert isinstance(cli, multilevelcli.MultiLevelArgParse)
        cli.add_option("t", "treelevels", opttype=int, default=7, description="max tree levels to process")
        cli.add_option("q", "quiet", description="do not emit messages")
        cli.add_command("list")
        ns = cli.parse()

        if str(ns.command()) == "list":
            print("This is the listing")
            print()
            print("--------------")

    except Exception as e:
        #print(str(e))
        traceback.print_exc()
        sys.exit(1)
    print ("### Success! namespace='%s'" % str(ns))
    print ("ns: %s" % ns.ns())
    print ("group: %s" % ns.group())
    print ("command: %s" % ns.command())
    print ("args: %s" % ns.args())
    print ("opt: %s" % ns.opt())
