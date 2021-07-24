#include <sourcemod>
#include <json>
#include <SteamWorks>
#include <sdktools>
#include <multicolors>

ConVar gRelayConnection = null;
ConVar gRelayInterval = null;
ConVar gHostport = null;
ConVar gHibernate = null

JSON_Object gToPost = null;

int gTickTimer;
bool gActive;
bool gDidAutoShutoff;

public Plugin myinfo = {
	name = "CS:GO Discord Relay Client",
	author = "Derpius",
	description = "Relays chat to and from the relay server",
	version = "0.1.0",
	url = "https://github.com/Derpius/pythonsourceserverdiscordbot"
};

/*
	Helpers
*/
void CachePost(JSON_Object body)
{
	char nonce = 1;
	char key[64];
	IntToString(RoundToFloor(GetGameTime()), key, 62);
	key[62] = nonce;

	while (gToPost.HasKey(key)) {
		nonce++;

		char type[32];
		body.GetString("type", type, 32);
		if (nonce == 16 || (nonce > 5 && !StrEqual(type, "message") && !StrEqual(type, "custom"))) {
			PrintToServer("Preventing caching messages to avoid Discord rate limiting due to spam");
			return;
		}
		key[62] = nonce;
	}

	gToPost.SetObject(key, body);
}

bool NetworkString(const char[] body)
{
	char url[512] = "http://";
	char conString[505];
	gRelayConnection.GetString(conString, 505);
	StrCat(url, 512, conString);

	char port[6];
	gHostport.GetString(port, 6);

	// Prevent triggering RCON bruteforce ban by detecting circular connection string
	char invalidCons[2][16] = {"localhost:", "127.0.0.1:"};
	for (int i = 0; i < 2; i++) {
		StrCat(invalidCons[i], 16, port);
		if (StrEqual(conString, invalidCons[i])) {
			LogError("[Relay] Error: Tried to use the server's listen port as the relay connection (will trigger RCON bruteforce ban on localhost)");
			return false;
		}
	}

	Handle request = SteamWorks_CreateHTTPRequest(k_EHTTPMethodPOST, url);
	if (
		request &&
		SteamWorks_SetHTTPRequestHeaderValue(request, "Source-Port", port) &&
		SteamWorks_SetHTTPRequestRawPostBody(request, "application/json", body, strlen(body)) &&
		SteamWorks_SetHTTPCallbacks(request, HttpPOSTCallback) &&
		SteamWorks_SendHTTPRequest(request)
	) return true;

	CloseHandle(request);
	return false;
}

/*
	Events
*/
public void OnPluginStart()
{
	gTickTimer = 0;
	gActive = false;
	gDidAutoShutoff = false;

	PrintToServer("HTTP Relay Client Loaded!");

	// Register concmds
	RegAdminCmd("relay_start", StartRelay, ADMFLAG_ROOT);
	RegAdminCmd("relay_stop", StopRelay, ADMFLAG_ROOT);

	// Register cvars
	gRelayConnection = CreateConVar(
		"relay_connection",
		"localhost:8080",
		"Connection string of the relay server (max 504 chars, http:// prepended automatically)",
		FCVAR_ARCHIVE // Flags
	);
	gRelayInterval = CreateConVar(
		"relay_interval",
		"16",
		"How many ticks to wait between cache POSTs",
		FCVAR_ARCHIVE, // Flags
		true, 1.0        // float min
	);
	gHostport = FindConVar("hostport");
	gHibernate = FindConVar("sv_hibernate_when_empty");

	// Generate config
	AutoExecConfig(true, "plugin_discordrelay");

	// Instantiate JSON
	gToPost = new JSON_Object();

	// Hook
	AddCommandListener(OnChat, "say");
	HookEvent("player_death", OnPlayerDeath);
}

public void OnGameFrame()
{
	if (!gActive) return;

	gTickTimer = (gTickTimer + 1) % gRelayInterval.IntValue;
	if (gTickTimer == 0 && gToPost.Length > 0) {
		char output[1024*8]; // 8kb payload
		gToPost.Encode(output, 1024*8);
		if (NetworkString(output)) {
			json_cleanup_and_delete(gToPost);
			gToPost = new JSON_Object();
		}
	} else if (gTickTimer == RoundToFloor(float(gRelayInterval.IntValue) / 2.0)) {
		char url[512] = "http://";
		char conString[505];
		gRelayConnection.GetString(conString, 505);
		StrCat(url, 512, conString);

		char port[6];
		gHostport.GetString(port, 6);

		// Prevent triggering RCON bruteforce ban by detecting circular connection string
		char invalidCons[2][16] = {"localhost:", "127.0.0.1:"};
		for (int i = 0; i < 2; i++) {
			StrCat(invalidCons[i], 16, port);
			if (StrEqual(conString, invalidCons[i])) {
				LogError("[Relay] Error: Tried to use the server's listen port as the relay connection (will trigger RCON bruteforce ban on localhost)");
				return;
			}
		}

		Handle request = SteamWorks_CreateHTTPRequest(k_EHTTPMethodGET, url);
		if (!(
			request &&
			SteamWorks_SetHTTPRequestHeaderValue(request, "Source-Port", port) &&
			SteamWorks_SetHTTPCallbacks(request, HttpGETCallback) &&
			SteamWorks_SendHTTPRequest(request)
		)) CloseHandle(request);
	}
}

public Action OnPlayerDeath(Event event, const char[] eventName, bool dontBroadcast)
{
	char weapon[64];
	int victimId = event.GetInt("userid");
	int attackerId = event.GetInt("attacker");
	event.GetString("weapon", weapon, sizeof(weapon));

	char victimName[64];
	char attackerName[64];
	int victim = GetClientOfUserId(victimId);
	int attacker = GetClientOfUserId(attackerId);
	GetClientName(victim, victimName, sizeof(victimName));
	GetClientName(attacker, attackerName, sizeof(attackerName));

	JSON_Object body = new JSON_Object();
	body.SetString("type", "death");
	body.SetString("suicide", victim == attacker ? "1" : "0");
	body.SetString("noweapon", strlen(weapon) == 0 ? "1" : "0");

	body.SetString("victim", victimName);
	body.SetString("inflictor", weapon);
	body.SetString("attacker", attackerName);

	CachePost(body);
	return Plugin_Continue;
}

public void OnClientConnected(int client)
{
	char name[33];
	GetClientName(client, name, 33);

	JSON_Object body = new JSON_Object();
	body.SetString("type", "join");
	body.SetString("name", name);

	CachePost(body);

	// Edge case: if this join event will cause the server to exit hibernation, turn on the relay
	if (!gActive && gDidAutoShutoff && GetClientCount(false) == 1 && gHibernate.BoolValue) ServerCommand("relay_start");
}

public void OnClientDisconnect(int client)
{
	char name[33];
	GetClientName(client, name, 33);

	JSON_Object body = new JSON_Object();
	body.SetString("type", "leave");
	body.SetString("name", name);

	CachePost(body);

	// Edge case: if this leave event will cause the server to go into hibernation, turn off the relay
	if (gActive && GetClientCount(false) <= 2 && gHibernate.BoolValue) {
		gDidAutoShutoff = true;
		ServerCommand("relay_stop");
	}
}

/*
	HTTP Handlers
*/
void HttpPOSTCallback(Handle request, bool failed, bool successful, EHTTPStatusCode statusCode)
{
	if (statusCode != k_EHTTPStatusCode200OK) {
		PrintToServer("[Relay POST] Status Code: %u", statusCode);
		CloseHandle(request);
		return;
	}

	CloseHandle(request);
}

void HttpGETCallback(Handle request, bool failed, bool successful, EHTTPStatusCode statusCode)
{
	if (statusCode == k_EHTTPStatusCode200OK) {
		SteamWorks_GetHTTPResponseBodyCallback(request, HandleHTTPResponse)
	} else {
		PrintToServer("[Relay GET] Status Code: %u", statusCode)
	}

	CloseHandle(request);
}

void HandleHTTPResponse(const char[] body)
{
	if (StrEqual(body, "none")) return;

	JSON_Object response = json_decode(body);

	JSON_Array chat = view_as<JSON_Array>(response.GetObject("chat"));
	for (int i = 0; i < chat.Length; i++) {
		JSON_Array msg = view_as<JSON_Array>(chat.GetObject(i));
		char name[33]; // Discord names must be 1-32 chars, + null terminator
		msg.GetString(0, name, 33);

		char msgText[4001]; // Max message length with Nitro + null terminator
		msg.GetString(1, msgText, 4001);

		char colour[7] // Hex colour value + null terminator
		msg.GetString(2, colour, 7);

		char role[101] // Role limit is 100 chars + null terminator
		msg.GetString(3, role, 101);

		char msgTextClean[4001]; // Max message length with Nitro + null terminator
		msg.GetString(4, msgTextClean, 4001);

		PrintToServer("[Discord | %s] %s: %s", role, name, msgText);
		if (IsSource2009()) CPrintToChatAll("{purple}[Discord | %s] {#%s}%s{default}: %s", role, colour, name, msgTextClean);
		else CPrintToChatAll("{purple}[Discord | %s] {default}%s: %s", role, name, msgTextClean);
	}

	JSON_Array rcon = view_as<JSON_Array>(response.GetObject("rcon"));
	for (int i = 0; i < rcon.Length; i++) {
		char cmd[4001];
		rcon.GetString(i, cmd, 4001);
		ServerCommand(cmd);
	}

	json_cleanup_and_delete(response);
}

/*
	ConCmd Handlers
*/
public Action StartRelay(int client, int args)
{
	if (gActive) {
		ReplyToCommand(client, "Relay already running");
		return Plugin_Handled;
	}

	ReplyToCommand(client, "Relay started");
	NetworkString("{\"0\":{\"type\":\"custom\",\"body\":\"Relay client connected!\"}}");
	gActive = true;
	gDidAutoShutoff = false;
	return Plugin_Handled;
}

public Action StopRelay(int client, int args)
{
	// Send the cache
	char output[1024*8]; // 8kb payload
	gToPost.Encode(output, 1024*8);
	if (NetworkString(output)) {
		json_cleanup_and_delete(gToPost);
		gToPost = new JSON_Object();
	}

	if (!gActive) {
		ReplyToCommand(client, "Relay already disabled");
		return Plugin_Handled;
	}

	ReplyToCommand(client, "Relay stopped");
	NetworkString("{\"0\":{\"type\":\"custom\",\"body\":\"Relay client disconnected\"}}");
	gActive = false;
	return Plugin_Handled;
}

public Action OnChat(int client, const char[] command, int args)
{
	if (!gActive) return Plugin_Continue;

	JSON_Object body = new JSON_Object();

	char msg[256];
	GetCmdArgString(msg, 256);
	StripQuotes(msg);

	if (client == 0) {
		body.SetString("type", "custom");
		char formattedMsg[11 + 256];
		Format(formattedMsg, sizeof(formattedMsg), "[CONSOLE]: %s", msg);
		body.SetString("body", formattedMsg);
	} else {
		char plrName[33];
		GetClientName(client, plrName, 33);

		int team = GetClientTeam(client);

		char teamName[128]; // Not sure what the max team name length is so this is likely excessive
		GetTeamName(team, teamName, 128);

		char teamColStr[12]; // 9 chars for 255*3, 2 for commas, and 1 for \0
		Format(teamColStr, 12, "%u,%u,%u", 200, 200, 200);

		char steamId64[18];
		GetClientAuthId(client, AuthId_SteamID64, steamId64, 18);

		body.SetString("type", "message");
		body.SetString("name", plrName);
		body.SetString("message", msg);
		body.SetString("teamName", teamName);
		body.SetString("teamColour", teamColStr);
		body.SetString("steamID", steamId64);
	}

	CachePost(body);
	return Plugin_Continue;
}
