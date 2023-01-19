#Copyright Sean Hunter
#Using MIT License (see license file for detail)

import json, requests, ipaddress, dns.resolver, datetime
#Python3 way (currently broken)
import ping3
#Python2 way (currently the only non-broken way)
#import ping
from multiprocessing import Pool

#############################################################################
#DEAR USER - YOU MUST DEFINE EVERYTHING FROM HERE ###########################
#############################################################################

#How long to wait for ping responses
timeout = 2
#Currently configured for a local run against a Docker Netbox install
#Adjust to fit your environment (in prod, probably on port 80 or 443)
ip_addresses_url = "http://localhost:32768/api/ipam/ip-addresses/"
ip_prefixes_url = "http://localhost:32768/api/ipam/prefixes/"

#Authorization header
#This must be generated from the Netbox web UI at http://netbox/user/api-tokens/
header={"Authorization": "Token 0123456789abcdef0123456789abcdef01234567"}

#Set to:
#1 - Scan RFC1918 space (192.168.0.0/16, 172.16.0.0/12, 10.0.0.0/8)
#2 - Scan IP addresses defined in Netbox
#3 - Scan prefixes defined in Netbox
load_scanner_from_rfc1918_or_netbox = 3

#OK, don't touch this line
myResolver = dns.resolver.Resolver()
#But MAKE CERTAIN that this one fits your environment; there will be reverse
#DNS requests made to this(these) server(s)
myResolver.nameservers = ['192.168.0.1','172.16.0.1','10.0.0.1']

#Determines the number of simultaneous pings to execute during timeout
#This can have a *very* high impact on performance, and can impact system
#stability so it is advised to only mess with it if you really know what you
#are doing
numProcesses = 250

#############################################################################
#THROUGH HERE ###############################################################
#############################################################################

#NOTE: Current possible status for IP addresses in Netbox include:
#1 - Active
#2 - Reserved
#3 - Deprecated
#5 - DHCP
#Don't ask what happened to 4. I assume Jeremy Stretch murdered him, the poor fellow.

def threadedPingReverseSave(addr):
	#Drop trailing /xx
	ip = (addr['address'].split("/"))[0]
	#Run ping twice - first to ensure ARP completes before second ping goes through
	#this is often visible in labs where the first ping to a newly online device will fail
	
	#Python2
	#ping.do_one(ip, timeout)
	#rtt = ping.do_one(ip, timeout)
	#Python3
	ping3.ping(ip, timeout=timeout)
	rtt = ping3.ping(ip, timeout=timeout)
	
	#Create the appropriate search string for a PTR record by reversing the IP space and
	#adding in-addr.arpa to the query
	dnsreq = '.'.join(reversed(ip.split("."))) + ".in-addr.arpa"
	#If the ping failed...
	if rtt == None:
		print(ip + ": NO RESPONSE BEFORE ICMP TIMEOUT EXPIRY")
		#There's not a great answer here, so we're going to assume the IP is merely reserved
		#Feel free to adjust this to your needs
		addr['status']=2
		try:
			#Do a reverse DNS (aka pointer/PTR) query
			myResolver.query(dnsreq, "PTR")
			dnsreply = myResolver.query(dnsreq, "PTR").response.answer
			for i in dnsreply:
				for j in i.items:
					#Save the reply to the description
					addr['description'] = j.to_text().rstrip('.')
					#Always save IP addresses with a reverse.
					saveAddr(addr)
		except:
			#If there is no reply, set the description variable to...
			addr['description'] = "No reverse."
			#No ping, but it is an IP-address scan, so we should save the result
			#Otherwise, it's from a prefix or RFC1918 space, so do NOT save it
			#this allows you to programmatically pull free IP addresses as needed
			if load_scanner_from_rfc1918_or_netbox == 2:
				saveAddr(addr)
			#raise

	#If the ping succeeded...
	else:
		addr['status'] = 1
		try:
			#Do a reverse DNS (aka pointer/PTR) query
			myResolver.query(dnsreq, "PTR")
			dnsreply = myResolver.query(dnsreq, "PTR").response.answer
			for i in dnsreply:
				for j in i.items:
					#Save the reply to a description variable
					desc = j.to_text()
		except:
			#If there is no reply, set the description variable to...
			desc = "No reverse.."
			#raise
		print(ip + ": " + str(rtt) + "s and reverse: " + desc)
		#Remove the right-most period (DNS resolver returns one, e.g. example.com.)
		addr['description'] = desc.rstrip('.')
		#Always save successful pings
		saveAddr(addr)
	result = addr
	return result

def saveAddr(addr):
	print("entered saveAddr for " + addr['address'])
	if addr['isNew'] == "new":
		addr.pop('isNew', None)
		post = requests.post(ip_addresses_url, headers=header, json=addr)
		print(post.status_code)
		print(post.json())
	elif addr['isNew'] == "old":
		addr.pop('isNew', None)
		try:
			role = addr['role']['value']
			addr.pop('role', None)
			addr['role'] = role
		except:
			#Do nothing
			print("Role exception.")
		post = requests.put(ip_addresses_url + str(addr['id']) + "/", headers=header, json=addr)
		print(post.status_code)
		print(post.json())
	return addr

def mergeWithExisting(addr, listOfIps):
	for ip_addr in listOfIps:
		print("IP to match: " + addr['address'] + " and checking against IP: " + ip_addr['address'])
		if ip_addr['address'] == addr['address']:
			print("MATCH: " + json.dumps(ip_addr, indent=4))
			#Get 'id' from existing and stuff it in addr
			print(ip_addr['id'])
			addr['id'] = ip_addr['id']
			addr['isNew'] = "old"
	return addr

if __name__ == '__main__':
	start = datetime.datetime.now()
	if load_scanner_from_rfc1918_or_netbox == 1:
		#Load from RFC1918
		print("Not currently loading addresses from RFC1918, even though I was told to!!")
	if load_scanner_from_rfc1918_or_netbox == 2:
		#GET IP addresses from Netbox
		response = requests.get(ip_addresses_url, headers = header)
		listOfIpsWithMask = response.json()['results']
		while response.json()['next'] is not None:
			response = requests.get(response.json()['next'], headers = header)
			for ip in response.json()['results']:
				listOfIpsWithMask.append(ip)
		for ipaddr in listOfIpsWithMask:
			ipaddr['isNew'] = "old"
		print("Populated from list of existing IP addresses. No new ones will be scanned.")
	if load_scanner_from_rfc1918_or_netbox == 3:
		#GET IP prefixes from Netbox
		response = requests.get(ip_prefixes_url, headers = header)
		listOfPrefixes = response.json()['results']
		while response.json()['next'] is not None:
			response = requests.get(ip_prefixes_url, headers = header)
			for prefix in response.json()['results']:
				listOfPrefixes.append(prefix)
		print(json.dumps(listOfPrefixes, indent=4))
		listOfIps = []
		for prefixObj in listOfPrefixes:
			print(prefixObj['prefix'])
			#print(ipaddress.ip_network(prefixObj['prefix']).hosts())
			mask = prefixObj['prefix'].split("/")[1]
			for host in ipaddress.ip_network(prefixObj['prefix']).hosts():
				listOfIps.append({"address": str(host) + "/" + mask})
		listOfIpsWithMask = listOfIps
		print("List of IP's with mask: ")
		print(listOfIpsWithMask)
		print("List of existing IP addresses: ")
		ip_result = requests.get(ip_addresses_url, headers = header)
		listOfIps = ip_result.json()['results']
		while ip_result.json()['next'] is not None:
			ip_result = requests.get(ip_result.json()['next'], headers = header)
			for ip in ip_result.json()['results']:
				listOfIps.append(ip)
		print(json.dumps(listOfIps, indent=4))
		for ipaddr in listOfIpsWithMask:
			ipaddr['isNew'] = "new"
			ipaddr = mergeWithExisting(ipaddr, listOfIps)
			print(json.dumps(ipaddr, indent=4))
#		print "Stopping..." + None
	#Pretty print new copy for debugging
	print(json.dumps(listOfIpsWithMask, indent=4))
	#Multithread the process. This isn't to speed up "processing" but eliminate the 
	#wait on timeout expiry; adjust to speed up/slow down system.	
	pool = Pool(processes=numProcesses)
	#Here, we call isPingable for every entity in listOfIpsWithMask
	result = pool.map(threadedPingReverseSave, listOfIpsWithMask)
#Presently looking at solutions that can sort this mess by IP address... currently results are unsorted.
	print(result)
	print(json.dumps(result, indent=4))
#	r = requests.post(ip_addresses_url, headers=header, json={"address": "192.168.3.2", "status": "1"})
#	print r.status_code
#	print r.json()
	finish = datetime.datetime.now()
	print("Completed in: " + str(finish - start))
