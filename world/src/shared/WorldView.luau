--!strict
-- 결과는 1초 안에 보인다. 이 연출에는 판정/보상 권한이 없으며 다른 플레이어와 공유하지 않는다.
local TweenService = game:GetService("TweenService")
local WorldView = {}
local model: Model? = nil
local tweens: {Tween} = {}
local activeToken = ""
local resolvedToken = ""
local function make(parent: Instance, name: string, size: Vector3, position: Vector3, color: Color3): Part
    local p = Instance.new("Part")
    p.Name = name
    p.Anchored = true
    p.CanCollide = false
    p.CanTouch = false
    p.Size = size
    p.Position = position
    p.Color = color
    p.Material = Enum.Material.SmoothPlastic
    p.Parent = parent
    return p
end
local function reset()
    for _, tween in tweens do tween:Cancel() end
    table.clear(tweens)
    if model then model:Destroy() end
    local root = Instance.new("Model")
    root.Name = "LocalInspectionView"
    root.Parent = workspace
    model = root
    make(root, "Body", Vector3.new(1.4, 1.6, 0.9), Vector3.new(0, 2.9, -2.8), Color3.fromRGB(97, 143, 191))
    local head = make(root, "Head", Vector3.new(1.35, 1.35, 1.35), Vector3.new(0, 4.2, -2.8), Color3.fromRGB(243, 218, 174))
    head.Shape = Enum.PartType.Ball
    make(root, "EyeLeft", Vector3.new(0.12, 0.14, 0.08), Vector3.new(-0.25, 4.3, -2.16), Color3.fromRGB(30, 40, 56))
    make(root, "EyeRight", Vector3.new(0.12, 0.14, 0.08), Vector3.new(0.25, 4.3, -2.16), Color3.fromRGB(30, 40, 56))
    make(root, "Smile", Vector3.new(0.32, 0.07, 0.08), Vector3.new(0, 4.02, -2.13), Color3.fromRGB(30, 40, 56))
    make(root, "Door", Vector3.new(4, 5.7, 0.25), Vector3.new(0, 2.85, -5), Color3.fromRGB(64, 91, 112))
    make(root, "Stamp", Vector3.new(1.3, 0.15, 0.8), Vector3.new(2.4, 2.72, 0), Color3.fromRGB(121, 133, 152))
end
function WorldView.show(token: string, phase: string, verdict: string?)
    if activeToken ~= token or not model then
        activeToken = token
        resolvedToken = ""
        reset()
    end
    if phase ~= "resolved" or resolvedToken == token then return end
    resolvedToken = token
    local root = model :: Model
    local color = if verdict == "approve" then Color3.fromRGB(87, 201, 163)
        elseif verdict == "verify" then Color3.fromRGB(248, 196, 95) else Color3.fromRGB(232, 137, 123)
    local stamp = root:FindFirstChild("Stamp") :: BasePart
    stamp.Color = color
    stamp.Material = Enum.Material.Neon
    local offset = if verdict == "approve" then Vector3.new(0, 0, -3)
        elseif verdict == "verify" then Vector3.new(3.5, 0, 0) else Vector3.new(-3.5, 0, 0)
    for _, p in root:GetChildren() do
        if p:IsA("BasePart") then
            local destination = p.Position
            if p.Name == "Door" and verdict == "approve" then destination += Vector3.new(4.5, 0, 0)
            elseif p.Name ~= "Door" and p.Name ~= "Stamp" then destination += offset end
            local tween = TweenService:Create(p, TweenInfo.new(0.35, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {Position = destination})
            table.insert(tweens, tween)
            tween:Play()
        end
    end
end
return WorldView
