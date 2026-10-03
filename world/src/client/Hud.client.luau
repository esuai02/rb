--!strict
-- 현재 목표 하나만 보인다 (K5). 판정은 서버가 한다 — 클라이언트는 고른 칸·고른 단계만 보낸다.
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Text = require(ReplicatedStorage.Shared.Text)
local SignalRemote = ReplicatedStorage:WaitForChild("SignalRemote")
local SlopeRemote = ReplicatedStorage:WaitForChild("SlopeRemote")

local screen = Instance.new("ScreenGui")
screen.Name = "GateHud"
screen.ResetOnSpawn = false
screen.Parent = script.Parent

local goal = Instance.new("TextLabel")
goal.Name = "Goal"
goal.Text = Text.get("goal.signal_1")
goal.Parent = screen

-- 고른 칸을 서버에 알린다. 맞고 틀림은 서버가 정한다.
local function sendCell(x: number, y: number)
	SignalRemote:FireServer(x, y)
end

-- 고른 기울기 표현을 서버에 알린다. 어느 것이 맞는지는 서버가 정한다.
local function sendSlope(choice: string)
	SlopeRemote:FireServer(choice)
end

sendCell(2, 1)
sendSlope("expr.slope.rise_more")
