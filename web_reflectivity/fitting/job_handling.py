#pylint: disable=bare-except, invalid-name
"""
    Abstraction layer for handling fitting jobs
"""
import string
import os

def create_model_file(data_form, layer_forms, q_max=0.2):
    """
    """
    materials = ""
    layer_list = []
    ranges = ''
    for form in layer_forms:
        materials += "%s\n" % form.get_material()
        layer_list.append(form.get_layer())
        ranges += form.get_ranges(sample_name='sample')

    _layers = ' | '.join(layer_list)
    sample = "sample = ( %s )" % _layers
    sample_ranges = data_form.get_ranges(probe_name='probe')

    template_dir, _ = os.path.split(os.path.abspath(__file__))
    with open(os.path.join(template_dir, 'reflectivity_model.py.template'), 'r') as fd:
        template = fd.read()

        model_template = string.Template(template)
        script = model_template.substitute(REDUCED_FILE=data_form.cleaned_data['data_path'],
                                           Q_MAX=q_max,
                                           MATERIALS=materials,
                                           SAMPLE=sample,
                                           RANGES=ranges,
                                           SAMPLE_RANGES=sample_ranges)

    with open('/tmp/__model.py', 'w') as fd:
        fd.write(script)

    return script
