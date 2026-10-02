--!strict
-- 현재 목표 하나만 보인다 (K5). 판정은 서버가 한다 — 클라이언트는 고른 칸만 보낸다
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Text = require(ReplicatedStorage.Shared.Text)
local SignalRemote = ReplicatedStorage:WaitForChild("SignalRemote")

local goal = Instance.new("TextLabel")
goal.Text = "루미를 신호 칸으로 보내자"
goal.Parent = script.Parent

local function sendCell(x: number, y: number)
	SignalRemote:FireServer(x, y)
end

sendCell(2, 1)
