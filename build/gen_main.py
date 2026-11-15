# Gold Hunter - erzeugt Main.xml (AIXML) fuer das Top-Level-VI Main.vi.
#   4 Schleifen: Tasten (Event-Struktur -> Key_Send), Spiel (Engine_Tick 60 mal pro Sekunde, Frame_Pace), Bild (Render_Frame -> Screen), Ton (Audio_Block)
# Aufruf: python gen_main.py
from gh_lib import *

desc = ('Gold Hunter. Start: App_Init (queues, notifier), Game_Start (world, highscores), sprites, HUD and title pictures, Window_Setup, '
        'Audio_Start. Main runs in the user interface system: keys (Key Down / Key Up by ScanCode and the Stop button -> Key_Send -> queue) and '
        'picture (Render_Frame in its own system -> Screen). Game_Loop (standard: Engine_Tick 60 times per second, Frame_Pace) and '
        'Sound_Loop (other 2: Audio_Block) are subVIs with their own loop. Timing log of ticks and frames to Resources\Data. End: Esc on the title screen or Stop. '
        'Keys: arrows = walk, climb, choose letters; Space = jump; Enter = start; Esc/P = pause; Z U L U = cheat (all rooms lit, endless lives).')
TIMING_SAVE = f"""  <Constant type="string" value="{TIMING_RENDER}" outputs="value:520.v" uid="520" uid_parent="root"/>
  <Constant _name="no error" type="{ERR}" value="{ERR_V}" outputs="value:521.v" uid="521" uid_parent="root"/>
  <Call target="Timing_Save.vi" inputs="File name:520.v,Ms:332.v,Tick:335.v,error in:521.v" outputs="error out:" uid="522" uid_parent="root"/>
"""
SPRITE_LOADER = 'Blit_Load.vi' if FULL_BLIT else 'SpriteAtlas_Load.vi'
xml = f"""<VI _name="Main.vi" description="{esc(desc)}">
  <Constant _name="no error" type="{ERR}" value="{ERR_V}" outputs="value:4010.v" uid="4010" uid_parent="root"/>
  <Call target="App_Init.vi" inputs="error in:4010.v" outputs="Channels:11.k,error out:11.e" uid="11" uid_parent="root"/>
  <Call target="Game_Start.vi" inputs="error in:11.e" outputs="State:12.st,Rooms:12.rooms,error out:12.e" uid="12" uid_parent="root"/>
  <Call target="{SPRITE_LOADER}" inputs="error in:12.e" outputs="Sprites:13.spr,error out:13.e" uid="13" uid_parent="root"/>
  <Constant _name="HUD file" type="string" value="hud.png" outputs="value:14.v" uid="14" uid_parent="root"/>
  <Call target="Image_Load.vi" inputs="File name:14.v,error in:13.e" outputs="Image:15.hud,error out:15.e" uid="15" uid_parent="root"/>
  <Node _name="VI Server Reference" outputs="This VI:16.vi" type="{{LV.VI}}" uid="16" uid_parent="root"/>
  <Constant _name="Title file" type="string" value="title.png" outputs="value:20.v" uid="20" uid_parent="root"/>
  <Call target="Image_Load.vi" inputs="File name:20.v,error in:15.e" outputs="Image:21.title,error out:21.e" uid="21" uid_parent="root"/>
  <Call target="Window_Setup.vi" inputs="VI:16.vi,error in:21.e" outputs="error out:22.e" uid="22" uid_parent="root"/>
  <Call target="Audio_Start.vi" inputs="error in:22.e" outputs="Bank:17.bank,Task ID:17.task,Mixer:17.mx,error out:17.e" uid="17" uid_parent="root"/>
  <Constant _name="Nothing drawn yet" type="{RMEM}" value="{RMEM_V}" outputs="value:18.v" uid="18" uid_parent="root"/>
  <Constant _name="Start ms" type="uint32" value="0" outputs="value:19.v" uid="19" uid_parent="root"/>
  <Constant _name="Tick count" type="int32" value="0" outputs="value:23.v" uid="23" uid_parent="root"/>
  <Constant _name="No keys yet" type="int32" value="0" outputs="value:24.v" uid="24" uid_parent="root"/>
  <Constant type="int32" value="0" outputs="value:26.v" uid="26" uid_parent="root"/>
  <Constant type="int32" value="{TIMING_N}" outputs="value:27.v" uid="27" uid_parent="root"/>
  <Node _name="Initialize Array" inputs="element:26.v,dimension size:27.v" outputs="initialized array:25.z" uid="25" uid_parent="root"/>

  <Structure _name="While Loop" count="" uid="100" uid_parent="root" label="Keys">
    <Tunnel _id="In1" inputs="value:11.k" outputs="value:101.v" uid="101" uid_parent="100"/>
    <ShiftReg uid="102" uid_parent="100">
      <Left inputs="value:24.v" outputs="value:103.v" uid="103" uid_parent="102"/>
      <Right inputs="value:150.h" outputs="value:" uid="104" uid_parent="102"/>
    </ShiftReg>
    <Structure _name="Event Structure" uid="110" uid_parent="100">
      <CaseFrame selector=" Key Down " uid="111" uid_parent="110">
        <Node _name="Event Data Node" fields="ScanCode" outputs="ScanCode:112.sc" uid="112" uid_parent="111"/>
        <Node _name="To Long Integer" inputs="number:112.sc" outputs="32bit integer:113.sc" uid="113" uid_parent="111"/>
        <Constant type="bool" value="false" outputs="value:114.v" uid="114" uid_parent="111"/>
        <Tunnel _id="Out1" inputs="value:113.sc" uid="115" uid_parent="111"/>
        <Tunnel _id="Out2" inputs="value:114.v" uid="116" uid_parent="111"/>
        <Tunnel _id="Out3" inputs="value:114.v" uid="117" uid_parent="111"/>
      </CaseFrame>
      <CaseFrame selector=" Key Up " uid="120" uid_parent="110">
        <Node _name="Event Data Node" fields="ScanCode" outputs="ScanCode:121.sc" uid="121" uid_parent="120"/>
        <Node _name="To Long Integer" inputs="number:121.sc" outputs="32bit integer:122.sc" uid="122" uid_parent="120"/>
        <Constant type="bool" value="true" outputs="value:123.v" uid="123" uid_parent="120"/>
        <Constant type="bool" value="false" outputs="value:124.v" uid="124" uid_parent="120"/>
        <Tunnel _id="Out1" inputs="value:122.sc" uid="125" uid_parent="120"/>
        <Tunnel _id="Out2" inputs="value:123.v" uid="126" uid_parent="120"/>
        <Tunnel _id="Out3" inputs="value:124.v" uid="127" uid_parent="120"/>
      </CaseFrame>
      <CaseFrame selector=" &quot;Stop&quot;\\3A Value Change " uid="130" uid_parent="110">
        <Control _name="Stop" type="bool" style="latched" value="false" outputs="value:131.v" uid="131" uid_parent="130"/>
        <Constant type="int32" value="-1" outputs="value:132.v" uid="132" uid_parent="130"/>
        <Constant type="bool" value="false" outputs="value:133.v" uid="133" uid_parent="130"/>
        <Tunnel _id="Out1" inputs="value:132.v" uid="134" uid_parent="130"/>
        <Tunnel _id="Out2" inputs="value:133.v" uid="135" uid_parent="130"/>
        <Tunnel _id="Out3" inputs="value:131.v" uid="136" uid_parent="130"/>
      </CaseFrame>
      <Tunnel _id="Out1" outputs="value:141.sc" uid="141" uid_parent="110"/>
      <Tunnel _id="Out2" outputs="value:142.up" uid="142" uid_parent="110"/>
      <Tunnel _id="Out3" outputs="value:143.quit" uid="143" uid_parent="110"/>
    </Structure>
    <Constant _name="no error" type="{ERR}" value="{ERR_V}" outputs="value:145.v" uid="145" uid_parent="100"/>
    <Call target="Key_Send.vi" inputs="Channels:101.v,ScanCode:141.sc,Released:142.up,Quit:143.quit,History:103.v,error in:145.v" outputs="Quit out:150.q,History out:150.h,error out:" uid="150" uid_parent="100"/>
    <Condition inputs="value:150.q" value="stop" uid="151" uid_parent="100"/>
  </Structure>

  <Call target="Game_Loop.vi" inputs="Channels:11.k,State:12.st,Rooms:12.rooms,error in:22.e" outputs="error out:215.v" uid="215" uid_parent="root"/>

  <Structure _name="While Loop" count="300i.v" uid="300" uid_parent="root" label="Picture">
    <Tunnel _id="In1" inputs="value:11.k" outputs="value:301.v" uid="301" uid_parent="300"/>
    <Tunnel _id="In2" inputs="value:13.spr" outputs="value:302.v" uid="302" uid_parent="300"/>
    <Tunnel _id="In3" inputs="value:12.rooms" outputs="value:303.v" uid="303" uid_parent="300"/>
    <Tunnel _id="In4" inputs="value:15.hud" outputs="value:304.v" uid="304" uid_parent="300"/>
    <Tunnel _id="In5" inputs="value:21.title" outputs="value:305.v" uid="305" uid_parent="300"/>
    <ShiftReg uid="310" uid_parent="300">
      <Left inputs="value:19.v" outputs="value:311.v" uid="311" uid_parent="310"/>
      <Right inputs="value:320.ms" outputs="value:" uid="312" uid_parent="310"/>
    </ShiftReg>
    <ShiftReg uid="313" uid_parent="300">
      <Left inputs="value:22.e" outputs="value:314.v" uid="314" uid_parent="313"/>
      <Right inputs="value:320.e" outputs="value:315.v" uid="315" uid_parent="313"/>
    </ShiftReg>
    <ShiftReg uid="316" uid_parent="300">
      <Left inputs="value:18.v" outputs="value:317.v" uid="317" uid_parent="316"/>
      <Right inputs="value:320.mem" outputs="value:" uid="318" uid_parent="316"/>
    </ShiftReg>
    <ShiftReg uid="330" uid_parent="300">
      <Left inputs="value:25.z" outputs="value:331.v" uid="331" uid_parent="330"/>
      <Right inputs="value:337.a" outputs="value:332.v" uid="332" uid_parent="330"/>
    </ShiftReg>
    <ShiftReg uid="333" uid_parent="300">
      <Left inputs="value:25.z" outputs="value:334.v" uid="334" uid_parent="333"/>
      <Right inputs="value:338.a" outputs="value:335.v" uid="335" uid_parent="333"/>
    </ShiftReg>
    <Call target="Render_Frame.vi" inputs="Channels:301.v,Sprites:302.v,Hud:304.v,Title:305.v,Memory:317.v,Last ms:311.v,error in:314.v" outputs="Picture:320.pic,Memory out:320.mem,FPS:320.fps,Now ms:320.ms,Stop:320.stop,Tick:320.tk,error out:320.e" uid="320" uid_parent="300"/>
    <Constant type="int32" value="{TIMING_N}" outputs="value:339.v" uid="339" uid_parent="300"/>
    <Node _name="Quotient &amp; Remainder" inputs="x:300i.v,y:339.v" outputs="x-y*floor(x/y):336.r,floor(x/y):" uid="336" uid_parent="300"/>
    <Node _name="To Long Integer" inputs="number:320.ms" outputs="32bit integer:340.ms" uid="340" uid_parent="300"/>
    <Node _name="Replace Array Subset" inputs="array:331.v,new element/subarray:340.ms,index:336.r" outputs="output array:337.a" uid="337" uid_parent="300"/>
    <Node _name="Replace Array Subset" inputs="array:334.v,new element/subarray:320.tk,index:336.r" outputs="output array:338.a" uid="338" uid_parent="300"/>
    <Indicator _name="Screen" type="picture" value="" inputs="value:320.pic" uid="321" uid_parent="300"/>
    <Indicator _name="FPS" type="double" value="0" inputs="value:320.fps" uid="322" uid_parent="300"/>
    <Condition inputs="value:320.stop" value="stop" uid="328" uid_parent="300"/>
  </Structure>

  <Control _name="Sound" type="bool" value="true" outputs="value:416.v" uid="416" uid_parent="root"/>
  <Call target="Sound_Loop.vi" inputs="Channels:11.k,Bank:17.bank,Task ID:17.task,Mixer:17.mx,Sound:416.v,error in:17.e" outputs="error out:415.v" uid="415" uid_parent="root"/>

  <Node _name="Merge Errors" inputs="error in:215.v,error in:315.v" outputs="error out:500.e" uid="500" uid_parent="root"/>
  <Call target="App_Close.vi" inputs="Channels:11.k,error in:500.e" outputs="error out:501.e" uid="501" uid_parent="root"/>
  <Call target="Audio_Close.vi" inputs="Task ID:17.task,error in:415.v" outputs="error out:" uid="502" uid_parent="root"/>
{TIMING_SAVE}  <Indicator _name="error out" type="{ERR}" value="{ERR_V}" inputs="value:501.e" uid="510" uid_parent="root"/>
</VI>
"""
xml = xml.replace('{TIMING_SAVE}', TIMING_SAVE if TIMING_LOG else '')
open(os.path.join(HERE, 'Main.xml'), 'w', encoding='utf-8').write(xml)
print('Main.xml', len(xml.splitlines()), 'lines')
