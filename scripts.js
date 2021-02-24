const inputBox = document.getElementById("text-entry")
const messageContainer = document.getElementById("message-container")

const messageTemplate = `
<img class="avatar" src="{AVATAR}">
<div class="content">
	<div class="message-header"><span class="username">{USERNAME}</span><span class="timestamp">{TIMESTAMP}</span></div>
	<div class="message-text">{CONTENT}</div>
</div>
`
const concatMessageTemplate = `
<div class="content">
	<div class="message-text">{CONTENT}</div>
</div>
`
let lastUser = {"id": "", "avatar": "", "name": "", "time": 0}
function addMessage(id, avatar, name, text) {
	const message = document.createElement("div")
	const timestamp = new Date()
	
	if (id != lastUser.id || timestamp.getTime() - lastUser.time > 420000 || avatar != lastUser.avatar || name != lastUser.name) {
		message.className = "message"
		message.innerHTML = messageTemplate.replace("{AVATAR}", avatar).replace("{USERNAME}", name).replace("{TIMESTAMP}", timestamp.toLocaleString()).replace("{CONTENT}", text)
		lastUser = {"id": id, "avatar": avatar, "name": name, "time": timestamp.getTime()}
	} else {
		message.className = "message concat"
		message.innerHTML = concatMessageTemplate.replace("{CONTENT}", text)
	}

	messageContainer.append(message)
}

inputBox.addEventListener("keyup", function(event) {
	if (event.key == "Enter" && inputBox.value) {
		event.preventDefault()
		addMessage("1", "https://cdn.akamai.steamstatic.com/steamcommunity/public/images/avatars/1c/1c7c3edea154c342d2e2e171c1f77702421639be_full.jpg", "Test", inputBox.value)
		inputBox.value = ""
	}
})