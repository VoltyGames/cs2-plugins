#include <ISmmPlugin.h>

#include <engine2/isource2server.h>

// Stands in for the partner's legacy plugins: SourceHook hooks on the engine functions VoltMod also hooks.
class LegacyDummy final : public ISmmPlugin
{
public:
    bool Load(PluginId id, ISmmAPI* ismm, char* error, size_t maxlen, bool late) override;
    bool Unload(char* error, size_t maxlen) override;
    void PrintCounts() const;

    const char* GetAuthor() override { return "meat.gg"; }
    const char* GetName() override { return "Legacy Dummy"; }
    const char* GetDescription() override
    {
        return "Counts SourceHook calls on GameFrame, ClientCommand and ClientPutInServer";
    }
    const char* GetURL() override { return ""; }
    const char* GetLicense() override { return "Public Domain"; }
    const char* GetVersion() override { return "1.0.0"; }
    const char* GetDate() override { return __DATE__; }
    const char* GetLogTag() override { return "LEGACY_DUMMY"; }

private:
    void OnGameFrame(bool simulating, bool firstTick, bool lastTick);
    void OnClientCommand(CPlayerSlot slot, const CCommand& args);
    void OnClientPutInServer(CPlayerSlot slot, const char* name, int type, uint64 xuid);

    IServerGameDLL* _server = nullptr;
    IServerGameClients* _gameClients = nullptr;
    unsigned long long _gameFrames = 0;
    unsigned long long _clientCommands = 0;
    unsigned long long _clientsPutInServer = 0;
};

static LegacyDummy thisPlugin;
PLUGIN_EXPOSE(LegacyDummy, thisPlugin);

SH_DECL_HOOK3_void(IServerGameDLL, GameFrame, SH_NOATTRIB, 0, bool, bool, bool);
SH_DECL_HOOK2_void(IServerGameClients, ClientCommand, SH_NOATTRIB, 0, CPlayerSlot, const CCommand&);
SH_DECL_HOOK4_void(IServerGameClients, ClientPutInServer, SH_NOATTRIB, 0, CPlayerSlot, const char*, int, uint64);

CON_COMMAND_F(legacy_dummy_status, "Print how often each legacy dummy hook has run", FCVAR_NONE)
{
    thisPlugin.PrintCounts();
}

bool LegacyDummy::Load(PluginId id, ISmmAPI* ismm, char* error, size_t maxlen, bool late)
{
    PLUGIN_SAVEVARS();

    GET_V_IFACE_CURRENT(GetEngineFactory, g_pCVar, ICvar, CVAR_INTERFACE_VERSION);
    GET_V_IFACE_ANY(GetServerFactory, _server, IServerGameDLL, INTERFACEVERSION_SERVERGAMEDLL);
    GET_V_IFACE_ANY(GetServerFactory, _gameClients, IServerGameClients, INTERFACEVERSION_SERVERGAMECLIENTS);

    SH_ADD_HOOK(IServerGameDLL, GameFrame, _server, SH_MEMBER(this, &LegacyDummy::OnGameFrame), true);
    SH_ADD_HOOK(IServerGameClients, ClientCommand, _gameClients, SH_MEMBER(this, &LegacyDummy::OnClientCommand), false);
    SH_ADD_HOOK(IServerGameClients, ClientPutInServer, _gameClients, SH_MEMBER(this, &LegacyDummy::OnClientPutInServer),
                true);

    META_CONVAR_REGISTER(FCVAR_RELEASE | FCVAR_GAMEDLL);
    META_CONPRINTF("[LEGACY_DUMMY] Loaded on plugin API %d\n", METAMOD_PLAPI_VERSION);
    return true;
}

bool LegacyDummy::Unload(char* error, size_t maxlen)
{
    SH_REMOVE_HOOK(IServerGameDLL, GameFrame, _server, SH_MEMBER(this, &LegacyDummy::OnGameFrame), true);
    SH_REMOVE_HOOK(IServerGameClients, ClientCommand, _gameClients, SH_MEMBER(this, &LegacyDummy::OnClientCommand),
                   false);
    SH_REMOVE_HOOK(IServerGameClients, ClientPutInServer, _gameClients,
                   SH_MEMBER(this, &LegacyDummy::OnClientPutInServer), true);

    META_CONPRINTF("[LEGACY_DUMMY] Unloaded\n");
    return true;
}

void LegacyDummy::PrintCounts() const
{
    META_CONPRINTF("[LEGACY_DUMMY] GameFrame %llu, ClientCommand %llu, ClientPutInServer %llu\n", _gameFrames,
                   _clientCommands, _clientsPutInServer);
}

void LegacyDummy::OnGameFrame(bool simulating, bool firstTick, bool lastTick)
{
    ++_gameFrames;
}

void LegacyDummy::OnClientCommand(CPlayerSlot slot, const CCommand& args)
{
    ++_clientCommands;
}

void LegacyDummy::OnClientPutInServer(CPlayerSlot slot, const char* name, int type, uint64 xuid)
{
    ++_clientsPutInServer;
}
