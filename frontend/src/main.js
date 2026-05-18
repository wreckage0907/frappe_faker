import { createApp } from "vue";

import App from "./App.vue";
import router from "./router";
import { initSocket } from "./socket";

import {
	Alert,
	Autocomplete,
	Badge,
	Button,
	Card,
	Dialog,
	Divider,
	ErrorMessage,
	FeatherIcon,
	FormControl,
	Input,
	ListView,
	LoadingText,
	MultiSelect,
	Progress,
	Sidebar,
	SidebarHeader,
	SidebarItem,
	SidebarSection,
	Spinner,
	Switch,
	Textarea,
	TextInput,
	Tooltip,
	frappeRequest,
	pageMetaPlugin,
	resourcesPlugin,
	setConfig,
} from "frappe-ui";

import "./index.css";

const globalComponents = {
	Alert,
	Autocomplete,
	Badge,
	Button,
	Card,
	Dialog,
	Divider,
	ErrorMessage,
	FeatherIcon,
	FormControl,
	Input,
	ListView,
	LoadingText,
	MultiSelect,
	Progress,
	Sidebar,
	SidebarHeader,
	SidebarItem,
	SidebarSection,
	Spinner,
	Switch,
	Textarea,
	TextInput,
	Tooltip,
};

const app = createApp(App);

setConfig("resourceFetcher", frappeRequest);

app.use(router);
app.use(resourcesPlugin);
app.use(pageMetaPlugin);

const socket = initSocket();
app.config.globalProperties.$socket = socket;

for (const key in globalComponents) {
	app.component(key, globalComponents[key]);
}

app.mount("#app");
