const inputBox = document.getElementById("text-entry")
const messageContainer = document.getElementById("message-container")

const messageTemplate = `
<img class="avatar" src="{AVATAR}">
<div class="content">
	<span class="username">{USERNAME}</span>
	<div class="message-text">{CONTENT}</div>
</div>
`
const concatMessageTemplate = `
<div class="content">
	<div class="message-text">{CONTENT}</div>
</div>
`
let lastUser = {"id": "", "avatar": "", "name": ""}
function addMessage(id, avatar, name, text) {
	const message = document.createElement("div")
	
	if (id != lastUser.id || avatar != lastUser.avatar || name != lastUser.name) {
		message.className = "message"
		message.innerHTML = messageTemplate.replace("{AVATAR}", avatar).replace("{USERNAME}", name).replace("{CONTENT}", text)
		lastUser = {"id": id, "avatar": avatar, "name": name}
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