--!strict
-- 공통 무대 하나. NPC/문/도장 연출은 클라이언트별로 그려 서로의 사건을 덮어쓰지 않는다.
local WorldBuilder = {}
local function part(parent: Instance, name: string, size: Vector3, position: Vector3, color: Color3): Part
    local p = Instance.new("Part")
    p.Name = name
    p.Anchored = true
    p.Size = size
    p.Position = position
    p.Color = color
    p.Material = Enum.Material.SmoothPlastic
    p.TopSurface = Enum.SurfaceType.Smooth
    p.BottomSurface = Enum.SurfaceType.Smooth
    p.Parent = parent
    return p
end
function WorldBuilder.build(): Model
    local old = workspace:FindFirstChild("InspectionWorld")
    if old and old:IsA("Model") then return old end
    local world = Instance.new("Model")
    world.Name = "InspectionWorld"
    world.Parent = workspace
    part(world, "Floor", Vector3.new(40, 1, 32), Vector3.new(0, -0.5, 0), Color3.fromRGB(34, 43, 58))
    part(world, "Desk", Vector3.new(8, 2.4, 2), Vector3.new(0, 1.2, 0), Color3.fromRGB(226, 216, 197))
    part(world, "DeskTop", Vector3.new(8.5, 0.25, 2.5), Vector3.new(0, 2.5, 0), Color3.fromRGB(52, 67, 86))
    part(world, "BackWall", Vector3.new(22, 10, 1), Vector3.new(0, 5, -7), Color3.fromRGB(28, 44, 62))
    part(world, "Trim", Vector3.new(20, 0.2, 0.15), Vector3.new(0, 6, -6.4), Color3.fromRGB(104, 195, 190))
    part(world, "LeftFrame", Vector3.new(0.3, 6, 0.3), Vector3.new(-2.2, 3, -5), Color3.fromRGB(130, 153, 165))
    part(world, "RightFrame", Vector3.new(0.3, 6, 0.3), Vector3.new(2.2, 3, -5), Color3.fromRGB(130, 153, 165))
    return world
end
return WorldBuilder
