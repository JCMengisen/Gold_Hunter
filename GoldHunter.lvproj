<?xml version='1.0' encoding='UTF-8'?>
<Project Type="Project" LVVersion="26008000">
	<Property Name="NI.LV.All.SaveVersion" Type="Str">Editor version</Property>
	<Property Name="NI.LV.All.SourceOnly" Type="Bool">true</Property>
	<Property Name="NI.Project.Description" Type="Str">Gold Hunter - jump and run in an underground pyramid</Property>
	<Item Name="My Computer" Type="My Computer">
		<Property Name="NI.SortType" Type="Int">3</Property>
		<Property Name="server.app.propertiesEnabled" Type="Bool">true</Property>
		<Property Name="server.control.propertiesEnabled" Type="Bool">true</Property>
		<Property Name="server.tcp.enabled" Type="Bool">false</Property>
		<Property Name="server.tcp.port" Type="Int">0</Property>
		<Property Name="server.tcp.serviceName" Type="Str">My Computer/VI Server</Property>
		<Property Name="server.tcp.serviceName.default" Type="Str">My Computer/VI Server</Property>
		<Property Name="server.vi.callsEnabled" Type="Bool">true</Property>
		<Property Name="server.vi.propertiesEnabled" Type="Bool">true</Property>
		<Property Name="specify.custom.address" Type="Bool">false</Property>
		<Item Name="Tests" Type="Folder">
			<Item Name="Test_Setup.vi" Type="VI" URL="../Tests/Test_Setup.vi"/>
			<Item Name="Snapshot_Run.vi" Type="VI" URL="../Tests/Snapshot_Run.vi"/>
			<Item Name="Test_Run.vi" Type="VI" URL="../Tests/Test_Run.vi"/>
		</Item>
		<Item Name="GH_Level.lvlib" Type="Library" URL="../Source/Level/GH_Level.lvlib"/>
		<Item Name="GH_Render.lvlib" Type="Library" URL="../Source/Render/GH_Render.lvlib"/>
		<Item Name="GH_Engine.lvlib" Type="Library" URL="../Source/Engine/GH_Engine.lvlib"/>
		<Item Name="GH_App.lvlib" Type="Library" URL="../Source/App/GH_App.lvlib"/>
		<Item Name="GH_Audio.lvlib" Type="Library" URL="../Source/Audio/GH_Audio.lvlib"/>
		<Item Name="Main.vi" Type="VI" URL="../Main.vi"/>
		<Item Name="Dependencies" Type="Dependencies"/>
		<Item Name="Build Specifications" Type="Build"/>
	</Item>
</Project>
