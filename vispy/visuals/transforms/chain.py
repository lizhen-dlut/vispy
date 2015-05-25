# -*- coding: utf-8 -*-
# Copyright (c) 2015, Vispy Development Team.
# Distributed under the (new) BSD License. See LICENSE.txt for more info.

from __future__ import division

from ..shaders import FunctionChain
from .base_transform import BaseTransform
from .linear import NullTransform


class ChainTransform(BaseTransform):
    """
    BaseTransform subclass that performs a sequence of transformations in
    order. Internally, this class uses shaders.FunctionChain to generate
    its glsl_map and glsl_imap functions.

    Arguments:

    transforms : list of BaseTransform instances
        See ``transforms`` property.
    """
    glsl_map = None
    glsl_imap = None

    Linear = False
    Orthogonal = False
    NonScaling = False
    Isometric = False

    def __init__(self, *transforms):
        super(ChainTransform, self).__init__()

        # Set input transforms
        trs = []
        for tr in transforms:
            if isinstance(tr, (tuple, list)):
                trs.extend(tr)
            else:
                trs.append(tr)
        self._transforms = trs

        # ChainTransform does not have shader maps
        self._shader_map = FunctionChain("transform_map_chain", [])
        self._shader_imap = FunctionChain("transform_imap_chain", [])
        self._rebuild_shaders()

    @property
    def transforms(self):
        """ The list of transform that make up the transform chain.
        
        The order of transforms is given such that the last transform in the 
        list is the first to be invoked when mapping coordinates through 
        the chain. 
        
        For example, the following two mappings are equivalent::
        
            # Map coordinates through individual transforms:
            trans1 = STTransform(scale=(2, 3), translate=(0, 1))
            trans2 = PolarTransform()
            mapped = trans1.map(trans2.map(coords))
            
            # Equivalent mapping through chain:
            chain = ChainTransform([trans1, trans2])
            mapped = chain.map(coords)
            
        """
        return self._transforms

    @transforms.setter
    def transforms(self, tr):
        if not isinstance(tr, list):
            raise TypeError("Transform chain must be a list")
        
        for t in self._transforms:
            t.changed.disconnect(self._subtr_changed)
        self._transforms = tr
        for t in self._transforms:
            t.changed.connect(self._subtr_changed)
        self._rebuild_shaders()
        self.update()

    @property
    def Linear(self):
        b = True
        for tr in self._transforms:
            b &= tr.Linear
        return b

    @property
    def Orthogonal(self):
        b = True
        for tr in self._transforms:
            b &= tr.Orthogonal
        return b

    @property
    def NonScaling(self):
        b = True
        for tr in self._transforms:
            b &= tr.NonScaling
        return b

    @property
    def Isometric(self):
        b = True
        for tr in self._transforms:
            b &= tr.Isometric
        return b

    def map(self, coords):
        """Map coordinates

        Parameters
        ----------
        coords : array-like
            Coordinates to map.

        Returns
        -------
        coords : ndarray
            Coordinates.
        """
        for tr in reversed(self.transforms):
            coords = tr.map(coords)
        return coords

    def imap(self, coords):
        """Inverse map coordinates

        Parameters
        ----------
        coords : array-like
            Coordinates to inverse map.

        Returns
        -------
        coords : ndarray
            Coordinates.
        """
        for tr in self.transforms:
            coords = tr.imap(coords)
        return coords

    def shader_map(self):
        return self._shader_map

    def shader_imap(self):
        return self._shader_imap
    
    def _rebuild_shaders(self):
        self._shader_map.functions = [tr.shader_map() for tr in reversed(self.transforms)]
        self._shader_imap.functions = [tr.shader_imap() for tr in self.transforms]

    def flat(self):
        """
        Return a simplified chain by expanding any nested chains.
        """
        transforms = self.transforms[:]
        new_chain = []
        while len(transforms) > 0:
            tr = transforms.pop(0)
            if isinstance(tr, ChainTransform):
                transforms = tr.transforms[:] + transforms
            else:
                new_chain.append(tr)
        
        return ChainTransform(new_chain)

    def simplified(self):
        """
        Return a simplified chain by joining adjacent transforms.
        If the result is a single transform, return that transform.
        """
        tr = self.flat()
        if len(tr.transforms) == 0:
            return NullTransform()
        cont = True
        tr = tr.transforms
        while cont:
            new_tr = [tr[0]]
            cont = False
            for t2 in tr[1:]:
                t1 = new_tr[-1]
                pr = t1 * t2
                if not isinstance(pr, ChainTransform):
                    cont = True
                    new_tr.pop()
                    new_tr.append(pr)
                else:
                    new_tr.append(t2)
            tr = new_tr

        if len(tr) == 1:
            return tr[0]
        else:
            return ChainTransform(tr)

    def append(self, tr):
        """
        Add a new transform to the end of this chain.

        Parameters
        ----------
        tr : instance of Transform
            The transform to use.
        """
        self.transforms.append(tr)
        tr.changed.connect(self._subtr_changed)
        self._rebuild_shaders()
        self.update()

    def prepend(self, tr):
        """
        Add a new transform to the beginning of this chain.

        Parameters
        ----------
        tr : instance of Transform
            The transform to use.
        """
        self.transforms.insert(0, tr)
        tr.changed.connect(self._subtr_changed)
        self._rebuild_shaders()
        self.update()

    def _subtr_changed(self, ev):
        """One of the internal transforms changed; propagate the signal. 
        """
        self.update()

    def __setitem__(self, index, tr):
        self._transforms[index].changed.disconnect(self._subtr_changed)
        self._transforms[index] = tr
        tr.changed.connect(self.subtr_changed)
        self._rebuild_shaders()
        self.update()

    def __mul__(self, tr):
        if isinstance(tr, ChainTransform):
            trs = tr.transforms
        else:
            trs = [tr]
        return ChainTransform(self.transforms+trs)

    def __rmul__(self, tr):
        if isinstance(tr, ChainTransform):
            trs = tr.transforms
        else:
            trs = [tr]
        return ChainTransform(trs+self.transforms)

    def __str__(self):
        names = [tr.__class__.__name__ for tr in self.transforms]
        return "<ChainTransform [%s] at 0x%x>" % (", ".join(names), id(self))
    
    def __repr__(self):
        tr = ",\n                 ".join(map(repr, self.transforms))
        return "<ChainTransform [%s] at 0x%x>" % (tr, id(self))
