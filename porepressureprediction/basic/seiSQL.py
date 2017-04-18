# -*- coding: utf-8 -*-
from __future__ import division, print_function
import sqlite3
import os
import json
import numpy as np


class SeisCube(object):
    def __init__(self, json_file):
        self.db_file = None
        self.json_file = json_file
        if self.json_file is not None:
            self._readJSON()
        self._inline_indices = None

    def _info(self):
        return "A seismic Data Cube\n" +\
               'In-line range: {} - {} - {}\n'.format(
                   self.startInline, self.endInline, self.stepInline) +\
               'Cross-line range: {} - {} - {}\n'.format(
                   self.startCrline, self.endCrline, self.stepCrline) +\
               'Z range: {} - {} - {}\n'.format(
                   self.startDepth, self.endDepth, self.stepDepth) +\
               "Inl/Crl bin size (m/line): {}/{}\n".format(
                   self.inline_bin, self.crline_bin) +\
               "SQL file location : {}\n".format(
                   os.path.abspath(self.db_file)) +\
               "Stored attributes: {}".format(self.attributes)

    def __str__(self):
        return self._info()

    def __repr__(self):
        return self._info()

    def _readJSON(self):
        with open(self.json_file, 'r') as fin:
            json_setting = json.load(fin)
            self.db_file = json_setting['db_file']
            self.startInline = json_setting['inline'][0]
            self.endInline = json_setting['inline'][1]
            self.stepInline = json_setting['inline'][2]
            self.startCrline = json_setting['crline'][0]
            self.endCrline = json_setting['crline'][1]
            self.stepCrline = json_setting['crline'][2]
            self.startDepth = json_setting['depth'][0]
            self.endDepth = json_setting['depth'][1]
            self.stepDepth = json_setting['depth'][2]
            self.inline_A = json_setting['Coordinate'][0][0]
            self.crline_A = json_setting['Coordinate'][0][1]
            self.east_A = json_setting['Coordinate'][0][2]
            self.north_A = json_setting['Coordinate'][0][3]
            self.inline_B = json_setting['Coordinate'][1][0]
            self.crline_B = json_setting['Coordinate'][1][1]
            self.east_B = json_setting['Coordinate'][1][2]
            self.north_B = json_setting['Coordinate'][1][3]
            self.inline_C = json_setting['Coordinate'][2][0]
            self.crline_C = json_setting['Coordinate'][2][1]
            self.east_C = json_setting['Coordinate'][2][2]
            self.north_C = json_setting['Coordinate'][2][3]
        self.nEast = (self.endInline - self.startInline) // \
            self.stepInline + 1
        self.nNorth = (self.endCrline - self.startCrline) // \
            self.stepCrline + 1
        self.nDepth = int((self.endDepth - self.startDepth) // self.stepDepth + 1)
        self._coordinate_conversion()

    def _coordinate_conversion(self):
        self.gamma_x = (self.east_B - self.east_A) / \
            (self.crline_B - self.crline_A)
        self.beta_x = (self.east_C - self.east_B) / \
            (self.inline_C - self.inline_B)
        self.alpha_x = self.east_A - \
            self.beta_x * self.inline_A - \
            self.gamma_x * self.crline_A
        self.gamma_y = (self.north_B - self.north_A) / \
            (self.crline_B - self.crline_A)
        self.beta_y = (self.north_C - self.north_B) / \
            (self.inline_C - self.inline_B)
        self.alpha_y = self.north_A - \
            self.beta_y * self.inline_A - \
            self.gamma_y * self.crline_A
        dist_ab = np.sqrt((self.north_B - self.north_A) *\
                          (self.north_B - self.north_A) + \
                          (self.east_B - self.east_A) * \
                          (self.east_B - self.east_A))
        dist_bc = np.sqrt((self.north_C - self.north_B) *\
                          (self.north_C - self.north_B) + \
                          (self.east_C - self.east_B) * \
                          (self.east_C - self.east_B))
        self.crline_bin = np.round(dist_ab / (self.crline_B - self.crline_A),
                                   decimals=2)
        self.inline_bin = np.round(dist_bc / (self.inline_C - self.inline_B),
                                   decimals=2)
    @property
    def depth(self):
        return np.arange(self.startDepth, self.endDepth+0.001, self.stepDepth)

    @property
    def attributes(self):
        try:
            with sqlite3.connect(self.db_file) as conn:
                cur = conn.cursor()
                cur.execute("""SELECT name FROM sqlite_master
                            WHERE type='table' ORDER BY name""")
                temp = cur.fetchall()
            attributelist = [item[0] for item in temp]
            attributelist.remove('position')
            return attributelist
        except Exception as inst:
            print(inst.args[0])
            return []

    @property
    def inline_indices(self):
        if self._inline_indices is None:
            self._inline_indices = np.arange(self.startInline,
                                             self.endInline+1,
                                             self.stepInline, dtype=np.int)
        return self._inline_indices


    def coord_2_line(self, coordinate):
        x = coordinate[0]
        y = coordinate[1]
        d = np.matrix([[x - self.alpha_x],
                       [y - self.alpha_y]])
        G = np.matrix([[self.beta_x, self.gamma_x],
                       [self.beta_y, self.gamma_y]])
        m = G.I * d
        # m = m.astype(int)

        inline, crline = m[0][0], m[1][0]
        param_in = (inline - self.startInline) // self.stepInline + \
            ((inline - self.startInline) % self.stepInline) // \
            (self.stepInline / 2)
        inline = self.startInline + self.stepInline * param_in
        param_cr = (crline - self.startCrline) // self.stepCrline + \
            ((inline - self.startCrline) % self.stepCrline) // \
            (self.stepCrline)
        crline = self.startCrline + self.stepCrline * param_cr
        return (inline, crline)

    def line_2_coord(self, inline, crline):
        x = self.alpha_x + self.beta_x * inline + self.gamma_x * crline
        y = self.alpha_y + self.beta_y * inline + self.gamma_y * crline
        return (x, y)

    def get_inline(self, inline, attr):
        try:
            if inline < self.startInline or inline > self.endInline:
                raise Exception("Inline number out of range.")
            with sqlite3.connect(self.db_file) as conn:
                cur = conn.cursor()
                cur.execute("SELECT attribute \
                             FROM position \
                             JOIN {table} \
                             ON position.id = {table}.id \
                             WHERE inline = {inl}".format(
                                                    table=attr, inl=inline))
                data = cur.fetchall()
            data = [d[0] for d in data]
            return np.array(data).reshape((self.nNorth, self.nDepth))
        except Exception as inst:
            print(inst.message)
            return []

    def get_crline(self, crline, attr):
        try:
            if crline < self.startCrline or crline > self.endCrline:
                raise Exception("Crossline number out of range.")
            with sqlite3.connect(self.db_file) as conn:
                cur = conn.cursor()
                cur.execute("SELECT attribute \
                             FROM position \
                             JOIN {table} \
                             ON position.id = {table}.id \
                             WHERE crline = {crl}".format(
                                                    table=attr, crl=crline))
                data = cur.fetchall()
            data = [d[0] for d in data]
            return np.array(data).reshape((self.nEast, self.nDepth))
        except Exception as inst:
            print(inst.message)
            return []

    def get_depth(self, depth, attr):
        try:
            if depth < self.startDepth or depth > self.endDepth:
                raise Exception("Depth out of range.")
            with sqlite3.connect(self.db_file) as conn:
                cur = conn.cursor()
                cur.execute("""SELECT attribute FROM position JOIN {table}
                            ON position.id = {table}.id
                            WHERE twt = {d}""".format(table=attr, d=depth))
                data = cur.fetchall()
            data = [d[0] for d in data]
            return data
        except Exception as inst:
            print(inst.message)
            return []

    def get_cdp(self, CDP, attr):
        try:
            il = CDP[0]
            cl = CDP[1]
            if il < self.startInline or il > self.endInline:
                raise Exception("Inline out of range.")
            if cl < self.startCrline or cl > self.endCrline:
                raise Exception("Crossline out of range.")
            with sqlite3.connect(self.db_file) as conn:
                cur = conn.cursor()
                cur.execute("""SELECT attribute FROM position JOIN {table}
                            ON position.id = {table}.id
                            WHERE inline = {inl} AND crline = {crl}
                            """.format(table=attr, inl=il, crl=cl))
                data = cur.fetchall()
            data = [d[0] for d in data]
            return data
        except Exception as inst:
            print(inst.message)
            return []

    def set_inline(self, inline, attr, data):
        """update attribute within an inline

           Parameters
           ----------
           inline : int
           attr : str
           data : list of float
        """
        val = [(d[0],) for d in data]
        with sqlite3.connect(self.db_file) as conn:
            cur = conn.cursor()
            cur.executemany("""UPDATE {table}
                           SET attribute = ?
                           WHERE inline={inl}
                           """.format(table=attr, inl=inline), val)

    def set_crline(self, crline, attr, data):
        val = [(d[0],) for d in data]
        with sqlite3.connect(self.db_file) as conn:
            cur = conn.cursor()
            cur.executemany("""UPDATE {table}
                           SET attribute = ?
                           WHERE crline={crl}
                           """.format(table=attr, crl=crline), val)

    def set_depth(self, depth, attr, data):
        val = [(d[0],) for d in data]
        with sqlite3.connect(self.db_file) as conn:
            cur = conn.cursor()
            cur.executemany("""UPDATE {table}
                           SET attribute = ?
                           WHERE twt={d}""".format(table=attr, d=depth), val)

    def set_cdp(self, CDP, attr, data):
        il = CDP[0]
        cl = CDP[1]
        val = [(d[0],) for d in data]
        with sqlite3.connect(self.db_file) as conn:
            cur = conn.cursor()
            cur.executemany("""UPDATE {table}
                           SET attribute = ?
                           WHERE inlne={inl} AND crline={crl}
                           """.format(table=attr, inl=il, crl=cl), val)

    def add_attr(self, attr):
        "Add an empty attribute to a SeisCube object"
        try:
            if attr in self.attributes:
                raise Exception("Attribute already exists, use another name")
            with sqlite3.connect(self.db_file) as conn:
                cur = conn.cursor()
                cur.execute("""CREATE TABLE {}(
                    id INTEGER PRIMARY KEY,
                    attribute REAL
                )""".format(attr))
        except Exception as inst:
            print(inst.message)

    def export_od(self, attr, fname):
        try:
            with open(fname, 'w') as fout:
                fout.write("{}\t{}\t{}\n".format(
                                            self.stepInline, self.stepCrline,
                                            self.stepDepth))
                with sqlite3.connect(self.db_file) as conn:
                    cur = conn.cursor()
                    for inl in range(self.startInline, self.endInline+1,
                                     self.stepInline):
                        for crl in range(self.startCrline, self.endCrline+1,
                                         self.stepCrline):
                            cur.execute(
                                "SELECT attribute \
                                 FROM position \
                                 JOIN {table} \
                                 ON position.id = {table}.id \
                                 WHERE inline = {inline} \
                                 AND crline = {crline}".format(table=attr,
                                                               inline=inl,
                                                               crline=crl))
                            temp = cur.fetchall()
                            if len(temp) == 0:
                                continue
                            else:
                                tempStr = list()
                                for i in range(len(temp)):
                                    tempStr.append(str(temp[i][0]))
                                data = '\t'.join(tempStr) + '\n'
                                string = str(inl) + '\t' + str(crl) + '\t'
                                fout.write(string + data)
        except Exception as inst:
            print(inst)
            print("failed to export")

    def export_gslib(self, attr, fname, title="seismic data"):
        """
        Output attributes to a gslib data file.
        A description of this file format could be found on
        'http://www.gslib.com/gslib_help/format.html'
        """
        try:
            with open(fname, 'w') as fout:
                fout.write(title+'\n')
                fout.write("4\nx\ny\nz\n")
                fout.write(attr+'\n')
                with sqlite3.connect(self.db_file) as conn:
                    cur = conn.cursor()
                    for inl in range(self.startInline, self.endInline+1,
                                     self.stepInline):
                        for crl in range(self.startCrline, self.endCrline+1,
                                         self.stepCrline):
                            cur.execute(
                                "SELECT attribute \
                                 FROM position \
                                 JOIN {table} \
                                 ON position.id = {table}.id \
                                 WHERE inline = {inline} \
                                 AND crline = {crline}".format(table=attr,
                                                               inline=inl,
                                                               crline=crl))
                            temp = cur.fetchall()
                            if len(temp) == 0:
                                continue
                            else:
                                x, y = self.line_2_coord(inl, crl)
                                for i in xrange(self.nDepth):
                                    tempList = [str(x), str(y), str(self.startDepth+self.stepDepth*i), str(temp[i][0])]
                                    fout.write('\t'.join(tempList) + '\n')
        except Exception as inst:
            print(inst)
            print("Failed to export.")