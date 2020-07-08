import numpy as np
import openpnm as op
from porespy.filters import trim_nonpercolating_paths
import collections


def tortuosity(im, axis, return_im=False, **kwargs):
    r"""
    Calculates tortuosity of given image in specified direction

    Parameters
    ----------
    im : ND-image
        The binary image to analyze with ``True`` indicating phase of interest
    axis : int
        The axis along which to apply boundary conditions
    return_im : boolean
        If ``True`` then the resulting tuple contains a copy of the input
        image with the concentration profile.

    Returns
    -------
    results :  tuple
        A named-tuple containing the calculated ``tortuosity`` value, the
        ``original_porosity`` of the image, the ``effective_porosity`` (with
        blind and non-percolating regions removed), and ``return_im`` is
        ``True``, then ``image`` will contain a copy of ``im`` with
        concentration values from the simulation.

    """
    if axis > (im.ndim - 1):
        raise Exception("Axis argument is too high")
    # Obtain original porosity
    porosity_orig = im.sum()/im.size
    # removing floating pores
    im = trim_nonpercolating_paths(im, inlet_axis=axis, outlet_axis=axis)
    # porosity is changed because of trimmimg floating pores
    porosity_true = im.sum()/im.size
    if porosity_true < porosity_orig:
        print('Caution, True porosity is:', porosity_true,
              'and volume fraction filled:',
              abs(porosity_orig-porosity_true)*100, '%')
    # cubic network generation
    net = op.network.CubicTemplate(template=im, spacing=1)
    # adding phase
    water = op.phases.Water(network=net)
    water['throat.diffusive_conductance'] = 1  # dummy value
    # running Fickian Diffusion
    fd = op.algorithms.FickianDiffusion(network=net, phase=water)
    # choosing axis of concentration gradient
    inlets = net['pore.coords'][:, axis] <= 1
    outlets = net['pore.coords'][:, axis] >= im.shape[axis]-1
    # boundary conditions on concentration
    C_in = 1.0
    C_out = 0.0
    fd.set_value_BC(pores=inlets, values=C_in)
    fd.set_value_BC(pores=outlets, values=C_out)
    if 'solver_family' in kwargs.keys():
        fd.settings.update(kwargs)
    else:
        fd.settings['solver_family'] = 'pyamg'
    fd.run()
    # calculating molar flow rate, effective diffusivity and tortuosity
    rate_out = fd.rate(pores=outlets)[0]
    rate_in = fd.rate(pores=inlets)[0]
    if not np.allclose(-rate_out, rate_in):
        raise Exception('Something went wrong, inlet and outlet rate do not match')
    delta_C = C_in - C_out
    L = im.shape[axis]
    A = np.prod(im.shape)/L
    N_A = A/L*delta_C
    Deff = rate_in/N_A
    tau = porosity_true/(Deff)
    result = collections.namedtuple('tortuosity_result', ['tortuosity',
                                                          'formation_factor',
                                                          'original_porosity',
                                                          'effective_porosity',
                                                          'image'])
    result.tortuosity = tau
    result.formation_factor = 1/Deff
    result.original_porosity = porosity_orig
    result.effective_porosity = porosity_true
    if return_im:
        conc = np.zeros([im.size, ], dtype=float)
        conc[net['pore.template_indices']] = fd['pore.concentration']
        conc = np.reshape(conc, newshape=im.shape)
        result.image = conc
    else:
        result.image = None
    return result
