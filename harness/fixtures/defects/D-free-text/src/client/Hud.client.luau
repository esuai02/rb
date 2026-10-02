--!strict
-- 현재 목표 하나만 보인다 (K5). 판정은 서버가 한다 — 클라이언트는 고른 칸만 보낸다
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Text = require(ReplicatedStorage.Shared.Text)
local SignalRemote = ReplicatedStorage:WaitForChild("SignalRemote")

local goal = Instance.new("TextLabel")
goal.Text = Text.get("goal.signal_2")
goal.Parent = script.Parent

local answer = Instance.new("TextBox")
answer.Parent = script.Parent

local function sendCell(x: number, y: number)
	SignalRemote:FireServer(x, y)
end

sendCell(2, 1)
