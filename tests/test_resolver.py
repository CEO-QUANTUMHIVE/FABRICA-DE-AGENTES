from motor_voz.brain.tenants.resolver import TENANT_POR_DEFECTO, tenant_de_la_sala


def test_extrae_el_tenant_del_nombre_de_sala():
    assert tenant_de_la_sala("demo-quantumhive-pipeline-a1b2c3") == "quantumhive"
    assert tenant_de_la_sala("demo-demo_capilar-gemini-f9e8d7") == "demo_capilar"


def test_nombre_sin_formato_cae_al_default():
    assert tenant_de_la_sala("sala-armada-a-mano") == TENANT_POR_DEFECTO


def test_nombre_vacio_cae_al_default():
    assert tenant_de_la_sala("") == TENANT_POR_DEFECTO
