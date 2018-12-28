class Vars:
    SOCKET_IMPOSSIBLE_REASON = ''
    interface_name = 'vcan0'
    ISOTP_SOCKET_POSSIBLE = False
    
    next_id = 10

def check_isotp_socket_possible():
    try:
        Vars.SOCKET_IMPOSSIBLE_REASON = ''
        import isotp
        import can
        s = isotp.socket()
        s.bind(Vars.interface_name, rxid=1, txid=2)
        s.close()
        Vars.ISOTP_SOCKET_POSSIBLE = True
    except Exception as e:
        Vars.SOCKET_IMPOSSIBLE_REASON = str(e)
        Vars.ISOTP_SOCKET_POSSIBLE = False

    return Vars.ISOTP_SOCKET_POSSIBLE

def isotp_socket_impossible_reason():
    return Vars.SOCKET_IMPOSSIBLE_REASON

def get_test_interface():
    return Vars.interface_name

def get_next_can_id_pair():
    pair = (Vars.next_id, Vars.next_id+1)
    Vars.next_id += 2
    return pair