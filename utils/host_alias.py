# need this bc https://informatics.ics.uci.edu/ is same as https://informatics.uci.edu/ ect...

# Dont know if they are technically alias bc x.uci.edu actually 302 temp redirect to x.ics.uci.edu
HOST_ALIASES = {
    "informatics.ics.uci.edu": "informatics.uci.edu",
    "cs.ics.uci.edu": "cs.uci.edu",
    "stat.ics.uci.edu": "stat.uci.edu"
}

def canonical_host(host):
    host = (host or "").lower().removeprefix("www.")
    return HOST_ALIASES.get(host, host) # get the non ics url for the queue, otherwise default to the host name