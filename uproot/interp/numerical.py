#!/usr/bin/env python

# Copyright (c) 2017, DIANA-HEP
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
# 
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
# 
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import sys

import numpy

from uproot.interp.interp import Interpretation

if sys.version_info[0] <= 2:
    string_types = (unicode, str)
else:
    string_types = (str, bytes)

class asdtype(Interpretation):
    def __init__(self, fromdtype, todtype=None, fromdims=(), todims=None):
        if isinstance(fromdtype, numpy.dtype):
            self.fromdtype = fromdtype
        elif isinstance(fromdtype, string_types) and len(fromdtype) > 0 and fromdtype[0] in (">", "<", "=", "|", b">", b"<", b"=", b"|"):
            self.fromdtype = numpy.dtype(fromdtype)
        else:
            self.fromdtype = numpy.dtype(fromdtype).newbyteorder(">")

        if todtype is None:
            self.todtype = self.fromdtype.newbyteorder("=")
        elif isinstance(todtype, numpy.dtype):
            self.todtype = todtype
        elif isinstance(todtype, string_types) and len(todtype) > 0 and todtype[0] in (">", "<", "=", "|", b">", b"<", b"=", b"|"):
            self.todtype = numpy.dtype(todtype)
        else:
            self.todtype = numpy.dtype(todtype).newbyteorder("=")

        self.fromdims = fromdims

        if todims is None:
            self.todims = self.fromdims
        else:
            self.todims = todims

    def to(self, todtype=None, todims=None):
        return asdtype(self.fromdtype, todtype, self.fromdims, todims)

    def toarray(self, array):
        return asarray(self.fromdtype, array, self.fromdims)

    def __repr__(self):
        args = []

        if self.fromdtype.byteorder == ">":
            args.append(repr(str(self.fromdtype)))
        else:
            args.append(repr(self.fromdtype))

        if self.todtype.newbyteorder(">") != self.fromdtype.newbyteorder(">"):
            if self.todtype.byteorder == "=":
                args.append(repr(str(self.todtype)))
            else:
                args.append(repr(self.todtype))

        if self.fromdims != ():
            args.append(repr(self.fromdims))

        if self.todims != self.fromdims:
            args.append(repr(self.todims))

        return "asdtype(" + ", ".join(args) + ")"

    def compatible(self, other):
        return isinstance(other, (asdtype, asarray)) and self.todtype == other.todtype and self.todims == other.todims

    def numitems(self, numbytes, numentries):
        return numbytes // self.fromdtype.itemsize

    def source_numitems(self, source):
        return _dimsprod(source.shape)

    def fromroot(self, data, offsets, local_entrystart, local_entrystop):
        array = data.view(self.fromdtype)
        if self.fromdims != ():
            product = _dimsprod(self.fromdims)
            assert len(array) % product == 0, "{0} % {1} == {2} != 0".format(len(array), product, len(array) % product)
            array = array.reshape((len(array) // product,) + self.fromdims)
        return array[local_entrystart:local_entrystop]

    def destination(self, numitems, numentries):
        product = _dimsprod(self.todims)
        if numitems % product != 0:
            raise ValueError("cannot reshape {0} items as {1} (groups of {2})".format(numitems, self.todims, product))
        return numpy.empty((numitems // product,) + self.todims, dtype=self.todtype)

    def fill(self, source, destination, itemstart, itemstop, skipentries, numentries):
        if self.fromdims == ():
            flattened_source = source
        else:
            flattened_source = source.reshape(len(source) * _dimsprod(self.fromdims))

        if self.todims == ():
            flattened_destination = destination
        else:
            flattened_destination = destination.reshape(len(destination) * _dimsprod(self.todims))

        flattened_destination[itemstart:itemstop] = flattened_source

    def clipitems(self, destination, itemstart, itemstop):
        return destination[itemstart:itemstop]

    def finalize(self, destination):
        return destination

class asarray(asdtype):
    def __init__(self, fromdtype, toarray, fromdims=()):
        if isinstance(fromdtype, numpy.dtype):
            self.fromdtype = fromdtype
        else:
            self.fromdtype = numpy.dtype(fromdtype).newbyteorder(">")
        self.toarray = toarray
        self.fromdims = fromdims

    @property
    def todtype(self):
        return self.toarray.dtype

    @property
    def todims(self):
        return self.toarray.shape[1:]

    def __repr__(self):
        args = []

        if self.fromdtype.byteorder == ">":
            args.append(repr(str(self.fromdtype)))
        else:
            args.append(repr(self.fromdtype))

        if self.todtype.byteorder == "=":
            args.append("<array dtype={0} at 0x{1:012x}>".format(repr(str(self.todtype)), id(self.todtype)))
        else:
            args.append("<array dtype={0} at 0x{1:012x}>".format(repr(self.todtype), id(self.todtype)))

        return "asarray(" + ", ".join(args) + ")"

    def destination(self, numitems, numentries):
        product = _dimsprod(self.todims)
        if numitems % product != 0:
            raise ValueError("cannot reshape {0} items as {1} (groups of {2})".format(numitems, self.todims, product))
        if _dimsprod(self.toarray.shape) < numitems:
            raise ValueError("cannot put {0} items into an array of {1} items".format(numitems, _dimsprod(self.toarray.shape)))
        return self.toarray, numitems // product

    def fill(self, source, destination, itemstart, itemstop, skipentries, numentries):
        super(asarray, self).fill(source, destination[0], itemstart, itemstop, skipentries, numentries)

    def clipitems(self, destination, itemstart, itemstop):
        array, stop = destination
        return super(asarray, self).clipitems(array, itemstart, itemstop), stop

    def finalize(self, destination):
        array, stop = destination
        return array[:stop]

def _dimsprod(dims):
    out = 1
    for x in dims:
        out *= x
    return out
