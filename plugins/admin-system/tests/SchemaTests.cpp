// The migrations and the generated specs are two views of one thing. Nothing else checks that a
// migration applies, or that a spec names a column the schema actually creates.

#include "Database/Tables/Schema.hpp"

#include <VoltMod/Core/Time/Scheduler.hpp>
#include <VoltMod/Database/Api.hpp>
#include <cstdint>
#include <doctest/doctest.h>
#include <filesystem>
#include <string>

namespace Tables = AdminSystem::Database::Tables;
using VoltMod::Database;
using VoltMod::RunMigrations;
using VoltMod::Scheduler;

static std::string MigrationsDir()
{
    return (std::filesystem::path(ADMIN_SYSTEM_DIR) / "migrations").string();
}

/** doctest evaluates the message eagerly, so this has to be safe on a successful result. */
template <class T>
static std::string ErrorText(const VoltMod::Result<T>& result)
{
    return result ? std::string{} : result.error().Detail;
}

/** Runs @p body against a fresh in-memory database with the plugin migrations applied. */
template <class Body>
static void WithMigratedDb(Body body)
{
    Scheduler scheduler;
    Database db(scheduler);
    REQUIRE(db.Connect({.driver = "sqlite", .path = ":memory:"}));

    auto migration = RunMigrations(db, MigrationsDir());
    REQUIRE(migration.Success);
    body(db, migration);
}

TEST_CASE("The migrations build the schema the generated specs describe")
{
    WithMigratedDb([](Database& db, const auto& migration) {
        CHECK(migration.Applied == 5);
        CHECK(migration.CurrentVersion == 5);

        // SQLite raises "no such column" when a spec and the schema disagree, so selecting
        // every column is the whole check. Matching no rows keeps it cheap.
        auto probe = db.Run("select-all-columns", [](auto& conn) {
            const auto count = [&conn](auto table) {
                int rows = 0;
                for ([[maybe_unused]] const auto& row :
                     conn(sqlpp::select(sqlpp::all_of(table)).from(table).where(table.id == 0)))
                {
                    ++rows;
                }
                return rows;
            };
            return count(Tables::AdminGroups{}) + count(Tables::Admins{}) + count(Tables::Players{}) +
                   count(Tables::Punishments{}) + count(Tables::Servers{}) + count(Tables::AdminServerGroups{}) +
                   count(Tables::AdminActivity{}) + count(Tables::PlayerReports{});
        });
        REQUIRE_MESSAGE(probe.has_value(), ErrorText(probe));
        CHECK(*probe == 0);

        CHECK(db.Run("seeded-group", [](auto& conn) {
                    const Tables::AdminGroups t;
                    int found = 0;
                    for ([[maybe_unused]] const auto& row :
                         conn(sqlpp::select(t.name).from(t).where(t.name == "super_admin")))
                    {
                        ++found;
                    }
                    return found;
                }).value_or(0) == 1);
    });
}

TEST_CASE("Applying the migrations twice changes nothing")
{
    WithMigratedDb([](Database& db, const auto&) {
        auto again = RunMigrations(db, MigrationsDir());
        CHECK(again.Success);
        CHECK(again.Applied == 0);
        CHECK(again.CurrentVersion == 5);
    });
}

TEST_CASE("An insert that supplies only the required columns is accepted")
{
    WithMigratedDb([](Database& db, const auto&) {
        // Every omitted column is one the generator gave a default. If it got one wrong,
        // sqlpp23 will not compile this or SQLite rejects the row.
        auto id = db.Run("minimal-punishment", [](auto& conn) {
            const Tables::Punishments t;
            return VoltMod::Insert(
                conn,
                sqlpp::insert_into(t).set(t.kind = "ban", t.targetSteamId = int64_t{76561198000000000},
                                          t.targetName = "someone", t.adminName = "console", t.reason = "testing"),
                "punishments");
        });
        REQUIRE_MESSAGE(id.has_value(), ErrorText(id));
        CHECK(*id > 0);
    });
}
