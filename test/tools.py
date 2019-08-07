class Vars:
    SOCKET_IMPOSSIBLE_REASON = ''
    interface_config = {
        "interface": "socketcan",
        "channel": "vcan0",
        "fd": False,
        "bitrate": 500000,
        "databitrate": 4000000
    }
    ISOTP_SOCKET_POSSIBLE = False
    CAN_FD_POSSIBLE = False
    CAN_FD_IMPOSSIBLE_REASON = ''
    ISOTP_STATUS_CHECKED = False

    next_id = 10


def check_isotp_socket_possible():
    try:
        Vars.SOCKET_IMPOSSIBLE_REASON = ''
        import isotp
        import can
        s = isotp.socket()
        s.bind(get_test_interface_config("channel"), rxid=1, txid=2)
        s.close()
        try:
            s = isotp.socket()
            s.set_ll_opts(mtu=isotp.tpsock.LinkLayerProtocol.CAN_FD)
            s.bind(get_test_interface_config("channel"), rxid=1, txid=2)
            s.close()
            Vars.CAN_FD_POSSIBLE = True
        except:
            Vars.CAN_FD_POSSIBLE = False
            Vars.CAN_FD_IMPOSSIBLE_REASON = 'Interface %s does not support MTU of %d.' % (get_test_interface_config("channel"), isotp.tpsock.LinkLayerProtocol.CAN_FD)
        Vars.ISOTP_SOCKET_POSSIBLE = True
    except Exception as e:
        Vars.SOCKET_IMPOSSIBLE_REASON = str(e)
        Vars.ISOTP_SOCKET_POSSIBLE = False

    Vars.ISOTP_STATUS_CHECKED = True
    return Vars.ISOTP_SOCKET_POSSIBLE

def is_can_fd_socket_possible():
    if Vars.ISOTP_STATUS_CHECKED == False:
        check_isotp_socket_possible()
    return Vars.CAN_FD_POSSIBLE

def isotp_socket_impossible_reason():
    return Vars.SOCKET_IMPOSSIBLE_REASON

def isotp_can_fd_socket_impossible_reason():
    return Vars.CAN_FD_IMPOSSIBLE_REASON


def get_test_interface_config(parameter_name=None):
    if parameter_name:
        return Vars.interface_config[parameter_name]
    else:
        return Vars.interface_config


def get_next_can_id_pair():
    pair = (Vars.next_id, Vars.next_id+1)
    Vars.next_id += 2
    return pair
