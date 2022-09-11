local references = {members = {}, roles = {}, emotes = {}}

local string_find, string_lower = string.find, string.lower
local _ipairs, _pairs = ipairs, pairs

local table_insert, table_sort = table.insert, table.sort

local function sortedFind(tbl, match)
	-- Get matches
	local matches = {}
	for _, v in _pairs(tbl) do
		local weight = match(v)
		if weight then table_insert(matches, {weight, v}) end
	end

	-- Sort
	table_sort(matches, function(a, b) return a[1] < b[1] end)

	-- Clean table
	for i, v in _ipairs(matches) do matches[i] = matches[i][2] end

	return matches
end

-- Members
-- Get the entire member table
function Relay.GetMembers()
	return references.members
end

-- Get a member by id
function Relay.GetMember(id)
	return references.members[id]
end

-- Get a list of members who match the given name (sorted by importance descending)
function Relay.FindMembersByName(name, caseSensitive, noPatterns)
	if caseSensitive == nil then caseSensitive = false end
	if noPatterns == nil then noPatterns = true end

	if not caseSensitive then name = string_lower(name) end

	return sortedFind(references.members, function(member)
		local matchIdx = string_find(
			caseSensitive and member:GetDisplayName() or string_lower(member:GetDisplayName()),
			name, 1, noPatterns
		)

		if not matchIdx then
			matchIdx = string_find(
				caseSensitive and member:GetUsername() or string_lower(member:GetUsername()),
				name, 1, noPatterns
			)

			if matchIdx then
				return matchIdx * 10 -- Heavily weight only username matches to the end
			end
		end

		return matchIdx
	end)
end

-- Roles
-- Get the entire roles table
function Relay.GetRoles()
	return references.roles
end

-- Get a role by id
function Relay.GetRole(id)
	return references.roles[id]
end

-- Get a list of roles that match the given name (sorted by importance descending)
function Relay.FindRolesByName(name, caseSensitive, noPatterns)
	if caseSensitive == nil then caseSensitive = false end
	if noPatterns == nil then noPatterns = true end

	if not caseSensitive then name = string_lower(name) end

	return sortedFind(references.roles, function(role)
		return string_find(
			caseSensitive and role:GetName() or string_lower(role:GetName()),
			name, 1, noPatterns
		)
	end)
end

-- Emotes
-- Get the entire emote table
function Relay.GetEmotes()
	return references.emotes
end

-- Get an emote by id
function Relay.GetEmote(id)
	return references.emotes[id]
end

-- Get a list of emotes that match the given name (sorted by importance descending)
function Relay.FindEmotesByName(name, caseSensitive, noPatterns)
	if caseSensitive == nil then caseSensitive = false end
	if noPatterns == nil then noPatterns = true end

	if not caseSensitive then name = string_lower(name) end

	return sortedFind(references.emotes, function(emote)
		return string_find(
			caseSensitive and emote:GetName() or string_lower(emote:GetName()),
			name, 1, noPatterns
		)
	end)
end

return references
