#!/usr/bin/env python
#
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
#

"""
This file contains the clone server utility which launches a new instance
of an existing server.
"""

import os
import subprocess
import sys
import time
import shutil

def clone_server(conn_val, new_data, new_port, new_id, rootpass,
                 mysqld_options=None, verbose=False, quiet=False):
    """ Clone an existing server

    This method creates a new instance of a running server using a datadir
    set to the new_data parametr, with a port set to new_port, server_id
    set to new_id and a root password of rootpass. You can also specify
    additional parameters for the mysqld command line as well as turn on
    verbose mode to display more diagnostic information during the clone
    process.

    The method will build a new base database installation from the .sql
    files used to construct a new installation. Once the database is
    created, the server will be started.

    dest_val[in]        a dictionary containing connection information
                        including:
                        (user, password, host, port, socket)
    new_data[in]        An existing path to create the new database and use
                        as datadir for new instance
    new_port[in]        Port number for new instance
    new_id[in]          Server_id for new instance
    rootpass[in]        Password for root user on new instance (optional)
    mysqld_options[in]  Additional command line options for mysqld
    verbose[in]         Print additional information during operation
                        (default is False)
    quiet[in]           If True, do not print messages.
                        (default is False)
    """

    from mysql.utilities.common.server import Server
    from mysql.utilities.exception import MySQLUtilError
    from mysql.utilities.common.tools import get_tool_path

    # Try to connect to the MySQL database server.
    server1 = Server(conn_val, "source")
    server1.connect()

    if not quiet:
        print "# Cloning the MySQL server running on %s." % conn_val["host"]

    # If datadir exists, delete it
    if os.path.exists(new_data):
        shutil.rmtree(new_data, True)

    # Create new data directory if it does not exist
    if not quiet:
        print "# Creating new data directory..."
    if not os.path.exists(new_data):
        try:
            res = os.mkdir(new_data)
        except:
            raise MySQLUtilError("Unable to create directory '%s'" % new_data)

    basedir = ""
    # Get basedir
    if not quiet:
        print "# Configuring new instance..."
    rows = server1.exec_query("SHOW VARIABLES LIKE 'basedir'")
    if rows:
        basedir = rows[0][1]
    else:
        raise MySQLUtilError("Unable to determine basedir of running server.")

    if not quiet:
        print "# Locating mysql tools..."
    mysqld_path = get_tool_path(basedir, "mysqld")
    mysqladmin_path = get_tool_path(basedir, "mysqladmin")
    mysql_basedir = get_tool_path(basedir, "share/english/errgmsg.sys",
                                  False, False)
    mysql_basedir = basedir
    if os.path.exists(basedir + "local/mysql/share/"):
        mysql_basedir += "local/mysql/"
    system_tables = get_tool_path(basedir, "mysql_system_tables.sql", False)
    system_tables_data = get_tool_path(basedir,
                                        "mysql_system_tables_data.sql", False)
    test_data_timezone = get_tool_path(basedir,
                                        "mysql_test_data_timezone.sql", False)
    help_data = get_tool_path(basedir, "fill_help_tables.sql", False)

    if verbose and not quiet:
        print "Location of files:"
        print "                      mysqld: %s" % mysqld_path
        print "                  mysqladmin: %s" % mysqladmin_path
        print "     mysql_system_tables.sql: %s" % system_tables
        print "mysql_system_tables_data.sql: %s" % system_tables_data
        print "mysql_test_data_timezone.sql: %s" % test_data_timezone
        print "        fill_help_tables.sql: %s" % help_data

    # Create the new mysql data with mysql_import_db-like process
    if not quiet:
        print "# Setting up empty database and mysql tables..."

    # Create the bootstrap file
    f_boot = open("bootstrap.sql", 'w')
    f_boot.write("CREATE DATABASE mysql;\n")
    f_boot.write("USE mysql;\n")
    f_boot.writelines(open(system_tables).readlines())
    f_boot.writelines(open(system_tables_data).readlines())
    f_boot.writelines(open(test_data_timezone).readlines())
    f_boot.writelines(open(help_data).readlines())
    f_boot.close()

    # Bootstap to setup mysql tables
    fnull = open(os.devnull, 'w')
    cmd = mysqld_path + " --no-defaults --bootstrap " + \
            " --datadir=%s --basedir=%s " % (new_data, mysql_basedir) + \
            " < bootstrap.sql"
    proc = None
    if verbose and not quiet:
        proc = subprocess.Popen(cmd, shell=True)
    else:
        proc = subprocess.Popen(cmd, shell=True, stdout=fnull, stderr=fnull)

    # Wait for subprocess to finish
    res = proc.wait()

    # Drop the bootstrap file
    if os.path.isfile("bootstrap.sql"):
        os.unlink("bootstrap.sql")

    # Start the instance
    if not quiet:
        print "# Starting new instance of the server..."
    cmd = mysqld_path + " --no-defaults "
    if mysqld_options:
        cmd += mysqld_options + " --user=root "
    cmd += "--datadir=%s " % (new_data)
    cmd += "--tmpdir=%s " % (new_data)
    cmd += "--pid-file=%s " % os.path.join(new_data, "clone.pid")
    cmd += "--port=%s " % (new_port)
    cmd += "--server-id=%s " % (new_id)
    cmd += "--basedir=%s " % (mysql_basedir)
    cmd += "--socket=%s/mysql.sock " % (new_data)
    if verbose and not quiet:
        proc = subprocess.Popen(cmd, shell=True)
    else:
        proc = subprocess.Popen(cmd, shell=True, stdout=fnull, stderr=fnull)

    # Try to connect to the new MySQL instance
    if not quiet:
        print "# Testing connection to new instance..."
    new_sock = None
    port_int = None
    if os.name == "posix":
        new_sock = os.path.join(new_data, "mysql.sock")
    port_int = int(new_port)

    conn = {
        "user"   : "root",
        "passwd" : "",
        "host"   : conn_val["host"],
        "port"   : port_int,
        "unix_socket" : new_sock
    }
    server2 = Server(conn, "clone")

    stop = 10 # stop after 10 attempts
    i = 0
    while i < stop:
        i += 1
        time.sleep(1)
        try:
            server2.connect()
            i = stop + 1
        except:
            pass
        finally:
            if verbose and not quiet:
                print "# trying again..."

    if i == stop:
        raise MySQLUtilError("Unable to communicate with new instance.")
    elif not quiet:
        print "# Success!"

    # Set the root password
    if rootpass:
        if not quiet:
            print "# Setting the root password..."
        if os.name == "posix":
            cmd = mysqladmin_path + " --no-defaults -v -uroot " + \
                  "--socket=%s password %s " % (new_sock, rootpass)
        else:
            cmd = mysqladmin_path + " --no-defaults -v -uroot " + \
                  "password %s --port=%s" % (rootpass, int(new_port))
        if verbose and not quiet:
            proc = subprocess.Popen(cmd, shell=True)
        else:
            proc = subprocess.Popen(cmd, shell=True,
                                    stdout=fnull, stderr=fnull)

        # Wait for subprocess to finish
        res = proc.wait()

    if not quiet:
        conn_str = "# Connection Information:\n"
        conn_str += "#  -uroot"
        if rootpass:
            conn_str += " -p%s" % rootpass
        if os.name == "posix":
            conn_str += " --socket=%s" % new_sock
        else:
            conn_str += " --port=%s" % new_port
        print conn_str
        print "#...done."

    fnull.close()
