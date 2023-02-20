-- Configuration file for the %TARGET_NAME% bindings generation.

local path = import "pl.path"

local src_dir = path.abspath(root_path .. "../sources")

local coreIncludeDir = src_dir .. "/nv%TARGET_NAME%/src"

local outputDir = src_dir .. "/lua_bindings/%TARGET_NAME%"

local cfg = {}

cfg.moduleName = "lua%TARGET_NAME%"
cfg.bindingName = "%TARGET_NAME%"
cfg.defaultNamespaceName = "%TARGET_NAME_LOWER%"

cfg.moduleRefs = {
    src_dir .. "/lua_bindings/Core"
}

cfg.traitsDir = path.abspath(root_path .. "../sources/lua/traits")

-- define asLuaModule to create a regular lua module:
-- cfg.moduleName = "luaCore"
-- cfg.asLuaModule = true

-- custom providers in this module:
cfg.custom_providers = { "nv::RefObject" }

local qt_inc_dir = "D:/Projects/NervProj/libraries/windows_clang/QT6-6.4.2/include"

cfg.includePaths = {
    qt_inc_dir,
    src_dir .. "/nvCore/src",
    src_dir .. "/nv%TARGET_NAME%/src",
    outputDir .. "/include",
}

cfg.inputPaths = {
    outputDir .. "/include/bind_context.h",
}

cfg.lls_lifdef_file = path.abspath(root_path .. "../dist/assets/lua_defs/%TARGET_NAME_LOWER%.lua")

-- cfg.inputPaths = { outputDir.."/include/core_interface.h", inputDir.."/base" }

-- cfg.inputInterfaces = { outputDir.."/interface/core_module.h" }
cfg.inputInterfaces = {}


cfg.cmakeConfig = {
    includeDirs = { "${QT6_DIR}/include", "../include", "${SRC_DIR}/nv%TARGET_NAME%/src", "${SRC_DIR}/nvCore/src",
        "${SRC_DIR}/lua_bindings/Core", "${SRC_DIR}/lua/traits" },
    libDirs = {},
    libs = { "nvCore", "nv%TARGET_NAME%" }
}

cfg.clangArgs = {
    "-Wno-pragma-once-outside-header",
    "-D__NERVBIND__",
    "-I" .. coreIncludeDir,
    "-I" .. outputDir .. "/include",
    "-I" .. outputDir .. "/interface",
    "-I" .. src_dir .. "/nvCore/src",
    "-I" .. qt_inc_dir,
    "-ID:/Projects/NervProj/libraries/windows_clang/fmt-9.1.1/include",
    -- "-I".. path.abspath(root_path.."../deps/msvc64/boost_1_68_0/include"),
    -- "-I".. path.abspath(root_path.."../deps/msvc64/LuaJIT-2.0.5/include/luajit-2.0"),
    -- "-I".. path.abspath(root_path.."../deps/msvc64/glm-0.9.9.2/include"),
}

cfg.outputDir = outputDir

local ignoredInputs = {
    "/sol/",
    "/rapidjson/",
    "/debug/",
    "/glm/",
    "noise/ARM/",
    "/lua/luna",
    "FastNoiseSIMD_internal%.h",
    "/MSVC/"
}

cfg.ignoreInputFile = function(filename)
    -- We should ignore that file if it contains one of the ignore patterns:
    local fname = filename:gsub("\\", "/")
    for _, p in ipairs(ignoredInputs) do
        if fname:find(p) then
            return true
        end
    end

    -- File is not ignored.
    return false
end

local ignoredClasses = {}

local allowedClasses = {
    -- Add classes here.
}

local preprocessClasses = function(ent)
    local name = ent:getFullName()
    if name == "void" then
        -- Keep the class.
        return
    end

    for _, p in ipairs(ignoredClasses) do
        if name:find(p) then
            ent:setIgnored(true)
            return
        end
    end

    for _, p in ipairs(allowedClasses) do
        if name:find(p) then
            return
        end
    end

    -- Ignore this entity:
    ent:setIgnored(true)
    return
end

local allowedFuncs = {
}

local preprocessFuncs = function(ent)
    local name = ent:getFullName()
    for _, p in ipairs(allowedFuncs) do
        if name:find(p) then
            return
        end
    end

    -- Ignore this entity:
    ent:setIgnored(true)
    -- logDEBUG("=> Ignoring entity ", name)
    return
end

local allowedEnums = {
}

local preprocessEnums = function(ent)
    local name = ent:getFullName()

    for _, p in ipairs(allowedEnums) do
        if name:find(p) then
            return
        end
    end

    -- Ignore this entity:
    ent:setIgnored(true)
    -- logDEBUG("=> Ignoring entity ", name)
    return
end


cfg.processEntities = function(root, typeManager)
    root:foreachClass(preprocessClasses)

    root:foreachGlobalFunction(preprocessFuncs)

    root:foreachGlobalEnum(preprocessEnums)
end

return cfg
