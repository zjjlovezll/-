%% FW/RW, FT/RT: FEM/Modal Method/Co-Running;

clc

for kk_Cal = 1:1:2

clearvars -except hwait kk_Cal
clear global 
if exist('hwait', 'var')
    close(hwait)
    clear hwait
end

Choose_Screen = 'Lab';
% Choose_Screen = 'Laptop';

InpPar.Choose_Turnout = '07(009)';
% InpPar.Choose_Turnout = 'CN18';

%% ===================== SearchPath and Gloabl Settings
% if strcmp(Choose_Screen, 'Lab')
%     addpath('E:\# Flex-Rigid-20200418\# FW_Rotation\Cal_FRF_FW_HSR')
%     if strcmp(InpPar.Choose_Turnout, '07(009)')
%         Path_1 = 'E:\# Flex-Rigid-20200418\# Abaqus Turnout Model\TurnoutScript_All_230730_S8a';
%     elseif strcmp(InpPar.Choose_Turnout, 'CN18')
%         Path_1 = 'G:\# Rail-Wheel Turnouts\2021-11-29 CM 2022\CN-AS-18\CN_AS_18_Script_T4_250812';
%     end
% else
%     addpath('D:\# Flex-Rigid-20200418\# FW_Rotation\Cal_FRF_FW_HSR')
%     if strcmp(InpPar.Choose_Turnout, '07(009)')
%         Path_1 = 'D:\# Flex-Rigid-20200418\# Abaqus Turnout Model\TurnoutScript_All_230730_S8a';
%     elseif strcmp(InpPar.Choose_Turnout, 'CN18')
%         Path_1 = 'D:\# Projects\2021-11-29 CM 2022\CN-AS-18\CN_AS_18_Script_T4_250812';
%     end
% end
% addpath(Path_1)
% addpath([Path_1, '\Model'])
addpath('WRProfile-07(009)-1_18\wheel')

if strcmp(InpPar.Choose_Turnout, '07(009)')
    addpath('WRProfile-07(009)-1_18\07(009)-Mileage')
    addpath('WRProfile-07(009)-1_18\07(009)-qjbg-20200418')
    addpath('WRProfile-07(009)-1_18\07(009)-zjg-20200418')
    addpath('WRProfile-07(009)-1_18\07(009)-zgyg-20200424')
    addpath('WRProfile-07(009)-1_18\07(009)-zgyg-20200509')
    addpath('WRProfile-07(009)-1_18\07(009)-zgyg-20250720')
    addpath('WRProfile-07(009)-1_18\07(009)-zgyg-20250722')
    addpath('WRProfile-07(009)-1_18\07(009)-cxg-20200422')
    addpath('WRProfile-07(009)-1_18\07(009)-cxg-20250801')
elseif strcmp(InpPar.Choose_Turnout, 'CN18')
    addpath('WRProfile-07(009)-1_18\CN18-Mileage')
    addpath('WRProfile-07(009)-1_18\CN18-jbg-220803')
    addpath('WRProfile-07(009)-1_18\CN18-jg')
    addpath('WRProfile-07(009)-1_18\CN18-cgxg-Re2')
    addpath('WRProfile-07(009)-1_18\CN18-zgyg-Add-250815')
end

Choose_Plot = 0;
InpPar.Type_Side = {'L', 'R'};
InpPar.Exp_WS = {'FF','FR','RF','RR'};
InpPar.Exp_DummyRail = {'L1','R1','R2','R3'};
InpPar.Exp_DummyRail_L = {'L1'};
InpPar.Exp_DummyRail_R = {'R1','R2','R3'};
InpPar.Exp_DummyRail_WheelSide = {'L','R','R','R'};
InpPar.N_ConPatch_L = 1;
InpPar.N_ConPatch_R = 3;
InpPar.N_ConPatch = length(InpPar.Exp_DummyRail);
InpPar.Color = {'r*','g*','b*','c*','r+','g+','b+','c+'};

InpPar.Type_DOF = {'UX', 'UY', 'UZ', 'ROTX', 'ROTY', 'ROTZ'};
if strcmp(InpPar.Choose_Turnout, '07(009)')
    InpPar.Type_Rail_All = {'zjbg', 'qjg_cgyg', 'zjg_zgyg', 'qjbg', 'cxg', 'dxg', 'cgjg', 'hg'}';
    InpPar.Type_Rail = {'zjbg', 'qjbg', 'zjg_zgyg', 'cxg'}';
elseif strcmp(InpPar.Choose_Turnout, 'CN18')
    InpPar.Type_Rail_All = {'zjbg', 'qjg_cgyg', 'zjg_zgyg', 'qjbg', 'cx', 'zghjg', 'cghjg', 'cgjg'};
    InpPar.Type_Rail = {'zjbg', 'qjbg', 'zjg_zgyg', 'cx'}';
end
InpPar.Type_Baseplate = {'Switch_L', 'Switch_R', ...
                                          'Closure_zjbg', 'Closure_qjg_cgyg', 'Closure_zjg_zgyg', 'Closure_qjbg', ...
                                           'Crossing_L', 'Crossing_Center', 'Crossing_R', ...
                                           'Plain_Thr_L', 'Plain_Thr_R', 'Plain_Div_L', 'Plain_Div_R'}';

% Normal wheel-rail contact algorighm
% InpPar.Type_Normal = 'Hertz';
% InpPar.Type_Normal = 'SIMHertz&ConDamp';
% InpPar.Type_Normal = 'Hertz&ConDamp';
InpPar.Type_Normal = 'STRIPES&ConDamp';

% InpPar.ConDamp = 'Lankarani–Nikravesh';
InpPar.ConDamp = 'Hu-Guo';
InpPar.ConDamp_Coff = 0.83;

% InpPar.ConDamp = 'Ref';
% InpPar.ConDamp_Coff = 2e4;

if kk_Cal==1
    InpPar.Type_simulation = 'Preload';
elseif kk_Cal==2
    InpPar.Type_simulation = 'Cal';
end

% Park, Newmark, Zhai, Houbolt
% InpPar.Int_Method = 'Zhai_Predict'; 
% InpPar.Int_Method = 'Newmark';
InpPar.Int_Method = 'Park';
% InpPar.Int_Method = 'Houbolt';

%% ===================== Track and Vehicle Parameters
% InpPar.Type_Track = 'Co-Running';          % Benchmark 
% InpPar.Type_Track = 'Flexible Track';        % Benchmark VSD SI
% InpPar.Type_Track = 'FT-FEM';
InpPar.Type_Track = 'FT-Modal';

% InpPar.Vlc = 250/3.6;	% 单位  m/s
% InpPar.Vlc = 275/3.6;	% 单位  m/s
% InpPar.Vlc = 282/3.6;	% 单位  m/s
% InpPar.Vlc = 291/3.6;	% 单位  m/s
InpPar.Vlc = 350/3.6;	% 单位  m/s
% InpPar.Vlc = 400/3.6;	% 单位  m/s
% InpPar.Vlc = 450/3.6;	% 单位  m/s

Par_Track = Par_TrackSystem(InpPar);

InpPar.VehicleDir = 'Face';
% InpPar.VehicleDir = 'Trail';

if strcmp(InpPar.VehicleDir, 'Trail')
    InpPar.Vlc = InpPar.Vlc*(-1);   % Trail
end

% InpPar.Type_Vehicle = 'CR400AF';
% InpPar.Type_Vehicle = 'CR400BF';
InpPar.Type_Vehicle = 'CRH380A_v6';
InpPar.N_RV = 35;
if strcmp(InpPar.Type_Vehicle, 'CRH380A_v6')
    Par_Vehicle = Par_Vehicle_CRH380A_v6(InpPar);
    InpPar.N_RV = InpPar.N_RV+16;                         % PS_VD*8 + Anti_Snake*4 + SS_LD*4
% elseif strcmp(InpPar.Type_Vehicle, 'CR400AF')
%     Par_Vehicle = Par_Vehicle_CR400AF(InpPar);    
%     InpPar.N_RV = InpPar.N_RV+20;                         % PS_VD*8 + Anti_Snake_Up*4 + Anti_Snake_Down*4 + SS_LD*4
% elseif strcmp(InpPar.Type_Vehicle, 'CR400BF')
%     Par_Vehicle = Par_Vehicle_CR400BF(InpPar);    
%     InpPar.N_RV = InpPar.N_RV+28;                         % PS_VD*8 + Anti_Snake_Up*4 + Anti_Snake_Down*4 + SS_LD*4 + SS_VD*8
end
Par_Vehicle.Distance_Vehicle = [0, 2*Par_Vehicle.Ll1, 2*Par_Vehicle.Ll2, 2*(Par_Vehicle.Ll1+Par_Vehicle.Ll2)];
 

%% ===================== Track Matrices
% global InpPar.ModeFreq InpPar.ModeShape_Mapping InpPar.ModeShape InpPar.Pos_Node InpPar.N_Node InpPar.DOF_Node
InpPar.Nw = 4;
if strcmp(InpPar.Type_Track,'Co-Running')          % 移动质量块模型
    % 构建质量、刚度和阻尼矩阵
    [M_track,K_track,C_track] = Matrix_RT(Par_Track.Mr1, Par_Track.Mr2, Par_Track.Mr3, Par_Track.Mr4, Par_Track.Ms, Par_Track.Jt, ...
     Par_Track.Krz1, Par_Track.Crz1, Par_Track.Krz2, Par_Track.Crz2, Par_Track.Krz3, Par_Track.Crz3, Par_Track.Krz4, Par_Track.Crz4,...
     Par_Track.Kry1, Par_Track.Cry1, Par_Track.Kry2, Par_Track.Cry2, Par_Track.Kry3, Par_Track.Cry3, Par_Track.Kry4, Par_Track.Cry4, ...
     Par_Track.Lt, Par_Track.Kzs, Par_Track.Czs, Par_Track.Kys, Par_Track.Cys, InpPar.Nw);
    InpPar.N_track = 11*InpPar.Nw;
    
else    
    % 读取道岔 FEM 模型模态集
    if strcmp(InpPar.Choose_Turnout, '07(009)')
%         [ModeFreq, ModeShape_Mapping, ModeShape, Pos_Node, N_Node, DOF_Node, Type_SpaceIron] = Get_Mat_Abaqus_220924(InpPar);
%         save Mat_FT_S6.mat ModeFreq ModeShape_Mapping ModeShape Pos_Node N_Node DOF_Node Type_SpaceIron
        load Mat_FT_S8b.mat
    elseif strcmp(InpPar.Choose_Turnout, 'CN18')
%         [ModeFreq, ModeShape_Mapping, ModeShape, Pos_Node, N_Node, DOF_Node, Type_SpaceIron] = Get_Mat_Abaqus_CN18_250812(InpPar);
%         save Mat_FT_CN18_T4.mat ModeFreq ModeShape_Mapping ModeShape Pos_Node N_Node DOF_Node Type_SpaceIron
        load Mat_FT_CN18_T4.mat
    end
    InpPar.ModeFreq = ModeFreq;
    InpPar.ModeShape_Mapping = ModeShape_Mapping;
    InpPar.ModeShape = ModeShape;
    InpPar.Pos_Node = Pos_Node;
    InpPar.N_Node = N_Node;
    InpPar.DOF_Node = DOF_Node;
    InpPar.Type_SpaceIron = Type_SpaceIron;
    clear ModeFreq ModeShape_Mapping ModeShape Pos_Node N_Node DOF_Node Type_SpaceIron
       
    if strcmp(InpPar.Type_Track,'FT-FEM')  % 基于有限单元法的道岔模型
        M_track = Mass_Rail.Cons_Trans;
        K_track = Stiff_Rail.Cons_Trans;
        C_track = (Par_Track.Rayleigh_Alpha*Mass_Rail.Free_Trans2 + Par_Track.Rayleigh_Beta*Stiff_Rail.Free_Trans2) + Damp_Rail.Cons_Trans;
        InpPar.N_track = DOF_Rail.Cons;
    elseif strcmp(InpPar.Type_Track,'FT-Modal')  % 基于模态叠加法的道岔模型
        % 设置截止频率
%         CutFreq_FT = 100;
%         CutFreq_FT = 250;
%         CutFreq_FT = 500;
%         CutFreq_FT = 750;
%         CutFreq_FT = 1000;
%         CutFreq_FT = 1500;
        CutFreq_FT = 2000;
        clear DR_Typical DR_Normal DR
        InpPar.N_track = length(find(InpPar.ModeFreq.FT_All(:,2)<=CutFreq_FT));
        
        %%% T1. DR_Typical
        DR_Typical = [];

        if strcmp(InpPar.Choose_Turnout, '07(009)')
            % T1a. S8b-DRv2
            DR_Typical = load('DR_S8b_v2_WeldAcc.txt');
            DR_Typical(:,3) = [];
            DR_Typical(DR_Typical(:,1)>InpPar.N_track,:) = [];
            DR_Typical = sortrows(DR_Typical, 1);
            x = InpPar.ModeFreq.FT_All(DR_Typical(:,1), 2);
            % S8b-DRv2_DRv4
%             xy_DR = [0, 75, 95, 105, 110, 2500
%                            0.15, 0.15, 0.05, 0.05, 0.50, 0.50]';
            % S8b-DRv5a
%             xy_DR = [0, 80, 95, 105, 110, 2500
%                            0.25, 0.25, 0.05, 0.05, 0.50, 0.50]';
            % S8b-DRv5b
%             xy_DR = [0, 80, 95, 105, 110, 2500
%                            0.25, 0.25, 0.05*3, 0.05*3, 0.50, 0.50]';
            % S8b-DRv5c
%             xy_DR = [0, 80, 95, 105, 110, 2500
%                            0.30, 0.30, 0.05*4, 0.05*4, 0.70, 0.70]';
            % S8b-DRv5(d)
            xy_DR = [0, 80, 95, 105, 110, 2500
                           0.30, 0.30, 0.05*4, 0.05*4, 0.70, 0.70]';
            DR_Typical(:,2) = interp1(xy_DR(:,1), xy_DR(:,2), x, 'linear');

            % T1b. S8b-DRv1
            DR_Typical_CRa = load('DR_S8b_v1_Crossing.txt');
            DR_Typical_CRa = sortrows(DR_Typical_CRa,1);
            DR_Typical_CRa(DR_Typical_CRa(:,1)>InpPar.N_track,:) = [];
            oup_repeat_CRa = [];
            for i1 = 1:1:size(DR_Typical_CRa,1)
                pos = find(DR_Typical(:,1)-DR_Typical_CRa(i1,1)==0, 1);
                if ~isempty(pos)
                    DR_Typical(pos,:) = DR_Typical_CRa(i1,:);
                    oup_repeat_CRa = [oup_repeat_CRa; DR_Typical_CRa(i1,:)];
                else
                    DR_Typical = [DR_Typical; DR_Typical_CRa(i1,:)];
                end
            end

            % T1c. 修正FRF: zjg_Z, cxg_Z, cgyg_Y, cxg_Y
%             DR_Typical_CRb = load('DR_S8b_v3_Crossing.txt');
%             DR_Typical_CRb = load('DR_S8b_v4_Crossing.txt');
            DR_Typical_CRb = load('DR_S8b_v5b_Crossing.txt');
            DR_Typical_CRb = sortrows(DR_Typical_CRb,1);
            DR_Typical_CRb(DR_Typical_CRb(:,1)>InpPar.N_track,:) = [];
            oup_repeat_CRb = [];
            for i1 = 1:1:size(DR_Typical_CRb,1)
                pos = find(DR_Typical(:,1)-DR_Typical_CRb(i1,1)==0, 1);
                if ~isempty(pos)
                    DR_Typical(pos,:) = DR_Typical_CRb(i1,:);
                    oup_repeat_CRb = [oup_repeat_CRb; DR_Typical_CRb(i1,:)];
                else
                    DR_Typical = [DR_Typical; DR_Typical_CRb(i1,:)];
                end
            end

            % T1d. 修正 DR_S8b_v2_WeldAcc 对 CR 阻尼比的影响
            DR_Typical_CRc = load('DR_S8b_v2_WeldAcc_ReCR.txt');
            DR_Typical_CRc = sortrows(DR_Typical_CRc,1);
            DR_Typical_CRc(DR_Typical_CRc(:,1)>InpPar.N_track,:) = [];
            DR_Typical_CRc(:,3) = [];
            oup_repeat_CRc = [];
            bools_CRa = false(size(DR_Typical_CRc,1),1);
            bools_CRb = false(size(DR_Typical_CRc,1),1);
            for i1 = 1:1:size(DR_Typical_CRc,1)
                bools_CRa(i1,1) = ~isempty(find(DR_Typical_CRa(:,1)-DR_Typical_CRc(i1,1)==0,1));
                bools_CRb(i1,1) = ~isempty(find(DR_Typical_CRb(:,1)-DR_Typical_CRc(i1,1)==0,1));
                pos = find(DR_Typical(:,1)-DR_Typical_CRc(i1,1)==0, 1);
                if ~isempty(pos)
                    DR_Typical(pos,:) = DR_Typical_CRc(i1,:);
                    oup_repeat_CRc = [oup_repeat_CRc; DR_Typical_CRc(i1,:)];
                else
                    DR_Typical = [DR_Typical; DR_Typical_CRc(i1,:)];
                end
            end


            %%% T2. DR_Normal
            % S5b-v6III
%             DR_Normal = [0, 75, 85, 95, 100 350, 375, 450, 475, 1000, 2000, 2500
%                                     0.15, 0.15, 0.05, 0.05, 0.02, 0.02, 0.10, 0.10, 0.02, 0.02, 0.01, 0.01]';
            % S8b-DR5(d)
            DR_Normal = [0, 80, 95, 105, 110, 200, 250, 350, 375, 450, 475, 600, 1000, 2000, 2500
                                    0.20, 0.20, 0.05*1, 0.05*1, 0.015, 0.015, 0.02, 0.02, 0.125, 0.125, 0.02, 0.0175, 0.015, 0.01, 0.005]';
            % Auto FT Damp
%             DR_Normal = [0, 2500
%                                     0.02, 0.02]';

        elseif strcmp(InpPar.Choose_Turnout, 'CN18')
            %%% T2. DR_Normal: $I_DampingRatio_T1
            DR_Normal = [0, 50, 100, 150, 300, 1000, 2500
                                    0.2, 0.2, 0.1, 0.02, 0.02, 0.02, 0.02]';
        end

        [M_track, K_track, C_track, DR, InpPar] = Matrix_Modal_FT_230313(InpPar, CutFreq_FT, DR_Normal, DR_Typical);
%         figure(19); clf
%         plot(DR(:,1), DR(:,2), '+');
%         grid on; set(gca,'XMinorTick','on','XScale','log');
    end
end


%% ===================== Vehicle Matrices
% global Par_FW
% InpPar.NM_FW = 31*1;         % RW-0；FW>0（任意一个大于零的数值）
InpPar.NM_FW = 0;         % RW-0；FW>0（任意一个大于零的数值）
Par_FW = struct;

if InpPar.NM_FW == 0
    if strcmp(InpPar.Type_Vehicle, 'CRH380A_v6')
        [M_vehicle, K_vehicle, C_vehicle{1,1}, C_vehicle_v0] = Matrix_Vehicle_RW_230409(InpPar, Par_Vehicle);
    elseif strcmp(InpPar.Type_Vehicle, 'CR400AF')
        [M_vehicle, K_vehicle, C_vehicle{1,1}, C_vehicle_v0] = Matrix_CR400AF_RW_230717(InpPar, Par_Vehicle);
    elseif strcmp(InpPar.Type_Vehicle, 'CR400BF')
        [M_vehicle, K_vehicle, C_vehicle{1,1}, C_vehicle_v0] = Matrix_CR400BF_RW_230722(InpPar, Par_Vehicle);
    end
else
    % 导入柔性轮对振型
%     CutFreq_FW = 100;
%     CutFreq_FW = 250;
%     CutFreq_FW = 500;
%     CutFreq_FW = 750;
%     CutFreq_FW = 1000;
%      CutFreq_FW = 1500;
    CutFreq_FW = 2000;
%     Load_ModeShape_FW(CutFreq_FW);
%     Load_ModeShape_FW_v2(CutFreq_FW)
%     Pos_Node Mass_FW Stiff_FW DOF_FW NM_FW ModeFreq ModeShape Ele_List Par_FW
    [InpPar, Par_FW] = Load_Rotation_FW(InpPar, CutFreq_FW);
    clear DR_FW
    DR_FW(:,1) = 1:1:InpPar.NM_FW;
    DR_FW(:,2) = 1e-2;                                   % Nodal = 1
    DR_FW([1 6 13 18 28 31],2) = 1e-3;      % Nodal = 0
    DR_FW([9:12, 22:25],2) = 1e-4;              % Nodal ≥ 2
    DR_FW(InpPar.NM_FW+1:size(DR_FW,1),:) = [];
    Choose_DR_FW = 0;
    [M_vehicle, K_vehicle, C_vehicle{1,1}, C_vehicle_v0] = Matrix_Vehicle_FW_230409(InpPar, Par_Vehicle, Par_FW, DR_FW, Choose_DR_FW);
end


%% ===================== System Matrices
DOF_sum = InpPar.N_track+InpPar.NM_FW*InpPar.Nw+InpPar.N_RV;
N_Patch_sum = InpPar.N_ConPatch*InpPar.Nw;
% 系统质量矩阵（位移变分为行，加速度为列）
Mxt = zeros(DOF_sum, DOF_sum);
Mxt(1:InpPar.N_track, 1:InpPar.N_track) = M_track;
Mxt(InpPar.N_track+1:end, InpPar.N_track+1:end) = M_vehicle;
% 系统刚度矩阵（位移变分为行，加速度为列）
Kxt = zeros(DOF_sum, DOF_sum);
Kxt(1:InpPar.N_track, 1:InpPar.N_track) = K_track;
Kxt(InpPar.N_track+1:end, InpPar.N_track+1:end) = K_vehicle;
% 系统阻尼矩阵（位移变分为行，加速度为列）
Cxt{1,1} = zeros(DOF_sum, DOF_sum);
Cxt{1,1}(1:InpPar.N_track, 1:InpPar.N_track) = C_track;
Cxt{1,1}(InpPar.N_track+1:end, InpPar.N_track+1:end) = C_vehicle{1,1};

% 计算车辆和轨道系统重力矩阵
if strcmp(InpPar.Type_Track, 'Co-Running')
    Pxt_Gravity = Gravity_Load_RT(InpPar, Par_Vehicle, Par_Track);
elseif strcmp(InpPar.Type_Track, 'FT-Modal') || strcmp(InpPar.Type_Track, 'FT-FEM')
    [Pxt_Gravity, Pxt_Gravity_Track] = Gravity_Load_ModalFT(InpPar, Par_Vehicle);
end

clear M_track K_track C_track

%% ===================== 计算前处理 A：定义数值迭代算法参数，预平衡赋值
% Range_drtaT = [1e-4, 5e-5, 2.5e-5, 1.25e-5, 6.25e-6, 3.125e-6, 3.125e-6/2, 3.125e-6/4];
Range_drtaT = 1e-4 ./ (2.^(0:1:12));
Newmark = struct;   Park = struct;  Zhai = struct;  Houbolt = struct;
tic
for i1 = 1:1:1
    for i2 = 1:1:length(Range_drtaT)
        drtaT=Range_drtaT(i2);           % 积分步长Δt  s
        if strcmp(InpPar.Int_Method, 'Newmark') || strcmp(InpPar.Type_simulation, 'Preload')
            Newmark.alpha = 0.50;              % 积分参数α，α≥0.50和β≥0.25(0.5+α)^2时，无条件稳定
            Newmark.beta = 0.25;               % 积分参数β，α≥0.50和β≥0.25(0.5+α)^2时，无条件稳定
            Newmark.A1{i1,i2} = 1/(Newmark.beta*drtaT*drtaT);
            Newmark.A2{i1,i2} = Newmark.alpha/(Newmark.beta*drtaT);
            Newmark.A3{i1,i2} = 1/(Newmark.beta*drtaT);
            Newmark.A4{i1,i2} = 1/(2*Newmark.beta)-1;
            Newmark.A5{i1,i2} = (drtaT/2)*(Newmark.alpha/Newmark.beta-2);
            Newmark.A6{i1,i2} = Newmark.alpha/Newmark.beta-1;
            % Newmark-β所用的(Kxt+A1*Mxt+A2*Cxt)逆矩阵inv(~)
            Newmark.Kyx{i1,i2} = inv((Kxt+Newmark.A1{i1,i2}*Mxt+Newmark.A2{i1,i2}*Cxt{i1,1}));
            for k1 = 3:1:4
                for k2 = 1:1:length(Range_drtaT)
                    Newmark.Kyx{k1,k2} = [];
                end
            end
        end
        if strcmp(InpPar.Int_Method, 'Park')
            % Park法所用的[A]矩阵的逆矩阵
            Park.Ajz{i1,i2} = inv((10/(6*drtaT))*(10/(6*drtaT))*Mxt+(10/(6*drtaT))*Cxt{i1,1}+Kxt);
            for k1 = 3:1:4
                for k2 = 1:1:length(Range_drtaT)
                    Park.Ajz{k1,k2} = [];
                end
            end
        elseif strcmp(InpPar.Int_Method, 'Houbolt')
            Houbolt.c0{i1,i2} = 2/(drtaT)^2;
            Houbolt.c1{i1,i2} = 11/(6*drtaT);
            Houbolt.c2{i1,i2} = 5/(drtaT)^2;
            Houbolt.c3{i1,i2} = 3/(drtaT);
            Houbolt.c4{i1,i2} = -2*Houbolt.c0{i1,i2};
            Houbolt.c5{i1,i2} = -Houbolt.c3{i1,i2}/2;
            Houbolt.c6{i1,i2} =  Houbolt.c0{i1,i2}/2;
            Houbolt.c7{i1,i2} = Houbolt.c3{i1,i2}/9;
            Houbolt.Kyx{i1,i2} = inv(Kxt + Houbolt.c0{i1,i2}*Mxt + Houbolt.c1{i1,i2}*Cxt{i1,1});
        elseif strcmp(InpPar.Int_Method, 'Zhai')
            % Zhai 方法所用系数矩阵
            Zhai.psi = 1/2;
            Zhai.phi = 1/2;
            Zhai.A1 = Kxt;
            Zhai.A2 = Cxt+Kxt*drtaT;
            Zhai.A3 = (1+Zhai.phi)*Cxt + (1/2+Zhai.psi)*Kxt*drtaT;
            Zhai.A4 = (Zhai.phi*Cxt + Zhai.psi*Kxt*drtaT);
            Zhai.B1 = inv(Mxt);
        elseif strcmp(InpPar.Int_Method, 'Zhai_Predict')
            % 新型预测-校正积分法
            Zhai_Predict.psi = 1/2;
            Zhai_Predict.phi = 1/2;
            Zhai_Predict.alpha = 0.50;              % 积分参数α，α≥0.50和β≥0.25(0.5+α)^2时，无条件稳定
            Zhai_Predict.beta = 0.25;               % 积分参数β，α≥0.50和β≥0.25(0.5+α)^2时，无条件稳定
            Zhai_Predict.B1 = inv(Mxt);
        end
    end
end
drtaT=Range_drtaT(1);
i_drtaT_PreviousStep = 3;
toc

% Integration Tolerance and other parameters
m1 = 1;                                                                     % 所有积分步迭代总次数指针项
if ~strcmp(InpPar.Int_Method, 'Zhai_Predict') && ~strcmp(InpPar.Int_Method, 'Zhai')
    xcs_t = 1;                                                                % 迭代不平衡存储指针项
    xcs_t_limit_1 = 2;                                                     % 每个积分步迭代次数上限
    xcs_t_limit_2 = 7;                                                     % 每个积分步迭代次数上限
    xcs_t_limit_3 = 11;                                                     % 每个积分步迭代次数上限
    Tolerance_Int_1 = 0.015;
    Tolerance_Int_2 = 0.0025;
    Tolerance_Int_3 = 0.001;
    ZP_IntError_Nor       = zeros(1);                              % 前后两步法向力误差，列为积分步xlcs，行为每一积分步迭代次数xcs
    ZP_IntError_NorTan = zeros(1);                               % 前后两步误差：蠕滑力和法向接触力合力
    P_WRForceError = zeros(N_Patch_sum, 3*2);     % (Cal)左右车轮编号及X、Y、Z三方向合力（行），用来求迭代误差
end

%% ===================== 计算前处理 B：定义计算起点和终点
% 起始和终点位置 / Storage Indicator: xlcs, xlzcs
if strcmp(InpPar.Type_simulation,'Cal')
    load Pre_CRH380A_009_Face_V350_zgygPf2_m2d5m.mat
    j0 = Pre.j1;                            % 导向轮对起点里程
    xlcs_start = 3;
    if strcmp(InpPar.VehicleDir, 'Trail')
        InpPar.FWc = 45;            % 导向轮对终点里程
%         InpPar.FWc = 95 + (Par_Vehicle.Ll1+Par_Vehicle.Ll2)*2;            % 导向轮对终点里程
    elseif strcmp(InpPar.VehicleDir, 'Face')
        InpPar.FWc = 110+(Par_Vehicle.Ll1+Par_Vehicle.Ll2)*2;            % 导向轮对终点里程
    end
elseif strcmp(InpPar.Type_simulation,'Preload')
    if strcmp(InpPar.VehicleDir, 'Trail')
        j0 = 150+4*(InpPar.Vlc*(-1)*3.6-350)/50;                               % 导向轮对起点里程
        InpPar.FWc = 110+(Par_Vehicle.Ll1+Par_Vehicle.Ll2)*2-0.1;            % 导向轮对终点里程
    elseif strcmp(InpPar.VehicleDir, 'Face')
        j0 = 32-2*(InpPar.Vlc*3.6-350)/50;                               % 导向轮对起点里程
        InpPar.FWc = 47.5+0.1;            % 导向轮对终点里程
    end
    xlcs_start = 1;
end
T = 0;
j1  = j0;                                   % 导向轮对位置(t=drtaT)
xlcs = xlcs_start;
xlzcs = ceil((InpPar.FWc-j0)*(-1)/InpPar.Vlc./drtaT)+xlcs_start;

%% ===================== 计算前处理 C：定义存储变量 & 系统预平衡
% C1. 计算结果矩阵，每列代表一个时间步长后的计算结果，每步长后添加一列，各初值需单独求解
Zwy  = zeros(DOF_sum, 4);
Zsd  = zeros(DOF_sum, 4);
Zjsd = zeros(DOF_sum, 4);
Pxt = zeros(DOF_sum, 1);
Pjc = zeros(N_Patch_sum, 2);                             % 左右车轮（行）两个相邻计算次数（列）法向接触力
Prhx = zeros(N_Patch_sum, 3);                           % 左右车轮编号及三项轮轨间蠕滑力（行）修正值，【列代表两个相邻计算次数？】
Prhxf = zeros(N_Patch_sum, 6);                          % 左右车轮编号及X、Y、Z三方向轮轨间蠕滑力（行）修正值分量，列代表蠕滑力和蠕滑力矩
Pjcc = zeros(N_Patch_sum, 1);                            % 法向接触力垂向分量
Pjch = zeros(N_Patch_sum, 1);                            % 法向接触力横向分量
drtaT_His = zeros(1,7);

% C2. Global Variables
% global ZP_Dyn ZP_Con ZP_Int
[ZP_Dyn, ZP_Con, ZP_Int] = DefineStruct_ZP(InpPar, xlzcs);
for i1 = 1:1:InpPar.Nw
    Con_WS.(InpPar.Exp_WS{i1}) = struct;
end
ZP_Dis = NaN(xlzcs, DOF_sum);
ZP_Vel = NaN(xlzcs, DOF_sum);
ZP_Acc = NaN(xlzcs, DOF_sum);
ZP_Load = NaN(xlzcs, DOF_sum);
ZP_NF = NaN(N_Patch_sum, xlzcs);

% C3. Save Options
Choose_Save = 1;    % 0-不保存，1-截断保存
clear Save_Mileage_Range Save_Mileage_Name
if strcmp(InpPar.VehicleDir, 'Face')
    Save_Mileage_Range = [-7.5, -2.5, 5.3, 20, 30, 40, 50, 52.5]+50;
elseif strcmp(InpPar.VehicleDir, 'Trail')
    Save_Mileage_Range = [-7.5, -2.5, 5.3, 10, 20, 30, 40, 50, 56, 60]+50+(Par_Vehicle.Ll1+Par_Vehicle.Ll2)*2;   % CR400AF, CR400BF
end
Save_Mileage_Range = sortrows(Save_Mileage_Range,1);
Save_Mileage_Name = cell(length(Save_Mileage_Range),1);
for kk = 1:1:length(Save_Mileage_Range)
    Tar = Save_Mileage_Range(kk)-50;
    if mod(Tar,1)==0
        Save_Mileage_Name{kk} = [num2str(Tar), 'm'];
    else
        Name_int = num2str(floor(Tar)-(sign(Tar)-1)/2);
        num_decimal = length(num2str(Tar))-find(num2str(Tar)=='.');
        Name_decimal = num2str( abs(mod(Tar,1*sign(Tar)))*10^(num_decimal) );
        Save_Mileage_Name{kk} = [Name_int, 'd', Name_decimal, 'm'];
    end
    temp = num2str(Tar);
    if strcmp(temp(1), '-')
        Save_Mileage_Name{kk}(1) = 'm';
    end
end

if strcmp(InpPar.VehicleDir, 'Face')
    k_save = find(j1-Save_Mileage_Range>=0, 1, 'last') + 1;
    if isempty(k_save)
        k_save = 1;
    end
elseif strcmp(InpPar.VehicleDir, 'Trail')
    k_save = find(j1-Save_Mileage_Range>=0, 1, 'last') ;
    if isempty(k_save)
        k_save = length(Save_Mileage_Range);
    end
end

% C4. Pre
if exist('Pre', 'var')
    Zwy(:,1:3) = Pre.Zwy;
    Zsd(:,1:3) = Pre.Zsd;
    Zjsd(:,1:3) = Pre.Zjsd;
    ZP_Dis(1:3,:) = Pre.ZP_Dis(end-2:end,:);
    ZP_Vel(1:3,:) = Pre.ZP_Vel(end-2:end,:);
    ZP_Acc(1:3,:) = Pre.ZP_Acc(end-2:end,:);
    ZP_Dyn.T(1:3,1) = (T-Pre.drtaT*2 : Pre.drtaT: T)';
            
    if isfield(Pre, 'drtaT_His') && length(Pre.drtaT_His)==length(drtaT_His)
        drtaT_His = Pre.drtaT_His;
    else
        drtaT_His = Pre.drtaT*ones(1,length(drtaT_His));
    end
    i_drtaT_PreviousStep = find(Range_drtaT==drtaT_His(end));
        
    Pjc(:,2) = Pre.NF(:,3);
    Pjcc = Pre.Pjcc;
    Pjch = Pre.Pjch;
    Prhxf = Pre.Prhxf;
    d0 = Pre.d0;
    for i1 = 1:1:InpPar.Nw
        Con_WS.(InpPar.Exp_WS{i1}) = Pre.Con_WS.(InpPar.Exp_WS{i1});
    end
    % ZP_Con
    for i2 = 1:1:InpPar.N_ConPatch
        T2 = InpPar.Exp_DummyRail{i2};
        if isfield(Pre.ZP_Con.RelVel_max, T2)
            ZP_Con .RelVel_max.(T2) = Pre.ZP_Con.RelVel_max.(T2);
            if strcmp(InpPar.Type_simulation,'Cal')
                for k1 = 1:1:size(ZP_Con.RelVel_max.(T2),1)
                    for k2 = 1:1:size(ZP_Con.RelVel_max.(T2),2)
                        if ~isempty(ZP_Con.RelVel_max.(T2){k1,k2})
                            ZP_Con .RelVel_max.(T2){k1,k2}(2:3,:) = repmat(ZP_Con.RelVel_max.(T2){k1,k2}(1,:), 2, 1);
                        end
                    end
                end
            end
        end
    end
    % Con_Rail_2, Con_Rail_1
    for i1 = 1:1:InpPar.Nw
        T1 = InpPar.Exp_WS{i1};
        for i2 = 1:1:length(InpPar.Type_Side)
            T2 = InpPar.Type_Side{i2};
            Target_1 = Pre.Con_WS.(T1).Con_rail_1.(T2);
            Target_wheel_2 = Pre.Con_WS.(T1).Con_wheel_2.(T2);
            if isfield(Pre.Con_WS.(T1), 'Con_rail_2')
                Target = Pre.Con_WS.(T1).Con_rail_2.(T2);
            else
                Target = Pre.Con_WS.(T1).Con_rail_1.(T2);
                if i2==1
                    Target(:,1) = Target(:,1)+0.753;
                else
                    Target(:,1) = Target(:,1)-0.753;
                end
            end
            for i3 = 1:1:size(Target,1)
                i_Patch = Pre.Con_WS.(T1).Normal_Force.(T2)(i3,4);
                T3 = InpPar.Exp_DummyRail{i_Patch};
                ZP_Con.Rail_2.(T3){i1,i3}(xlcs,:) = [Pre.j1, Target(i3,:)];
                ZP_Con.Rail_1.(T3){i1,i3}(xlcs,:) = [Pre.j1, Target_1(i3,:)];
                ZP_Con.Wheel_2.(T3){i1,i3}(xlcs,:) = [Pre.j1, Target_wheel_2(i3,:)];
            end        
        end        
    end
    
else
    % 设定静轮载作用下车体各部件的位移
    Pw = (Par_Vehicle.Mw/2+Par_Vehicle.Mb/4+Par_Vehicle.Mc/8)*9.81;
    GG_L = 3.86e-8.*(Par_Vehicle.R0).^(-0.115);
    zw = Pw^(2/3)*GG_L;    
    zt = ((Par_Vehicle.Mb/2+Par_Vehicle.Mc/4)*9.81) / (2*Par_Vehicle.K1z) + zw;
%     zc = (Par_Vehicle.Mc/4*9.81) / (Par_Vehicle.K2z+2*Par_Vehicle.K_SS_DPz) + zt;
    zc = (Par_Vehicle.Mc/4*9.81) / Par_Vehicle.K2z + zt;
    bools = false(N_Patch_sum,1);
    bools(1:InpPar.N_ConPatch:InpPar.N_ConPatch*3+1) = true;
    if strcmp(InpPar.VehicleDir, 'Face')
        bools(2:InpPar.N_ConPatch:InpPar.N_ConPatch*3+2) = true;
    else
        bools(4:InpPar.N_ConPatch:InpPar.N_ConPatch*3+4) = true;
    end
    Pjc(bools,1:2) = Pw;
    Pjcc(bools) = Pw*-1;
    Zwy(InpPar.N_track+InpPar.NM_FW*InpPar.Nw+[1,6,11,16],1) = zw;
    Zwy(InpPar.N_track+InpPar.NM_FW*InpPar.Nw+[21,26],1) = zt;
    Zwy(InpPar.N_track+InpPar.NM_FW*InpPar.Nw+31,1) = zc;

    % TEST!!! 串联弹簧-阻尼单元
    Zwy(InpPar.N_track+InpPar.NM_FW*InpPar.Nw+[36:1:43],1) = zw;
    if strcmp(InpPar.Type_Vehicle, 'CR400BF')
        Zwy(InpPar.N_track+InpPar.NM_FW*InpPar.Nw+[56:1:63],1) = zt;
    end
    
end


%% ===================== 计算前处理 D：线型、轨道不平顺、轮轨廓形、图形显示设置
% global TIrr InpPar.d_TIrr
% global InpPar.Mileage_sum InpPar.MileageInterp_Div InpPar.Profile_Bezier InpPar.SIP InpPar.num_interp_Bezier 
% global InpPar.WheelPro_ProCS

% D1. Layout, Par_Layout
InpPar.Type_Layout = 'Straight';
if strcmp(InpPar.Type_Layout, 'Curve')
    Par_Layout.R1 = inf; Par_Layout.R3 = inf; Par_Layout.R = 1100;
    Par_Layout.L_trans_1 = 0.25; Par_Layout.L_trans_2 = 0.25; Par_Layout.L_trans_3 = 0.1;
    Par_Layout.Yaw_trans = 26.8/5168;
    Par_Layout.Curve_start_1 = 50; Par_Layout.Curve_start_3 = 55.168;
    Par_Layout.Curve_start_2 = Par_Layout.Curve_start_1+Par_Layout.L_trans_2;
    Par_Layout.L_Str = Par_Layout.Curve_start_3-Par_Layout.Curve_start_2-Par_Layout.L_trans_2/2-Par_Layout.L_trans_3/2;
    % 求解 R2
    s = Par_Layout.L_trans_1;
    k1 = 1/Par_Layout.R1; k3 = 1/Par_Layout.R3;
    syms k2 fun_yaw_trans2b(k2)
    C1 = 1/3*Par_Layout.L_trans_2*(k2+k3);
    s2 = Par_Layout.L_trans_2;
    fun_yaw_trans2b(k2) = (2*k2-3*k3)*(s2) + 2/(3*Par_Layout.L_trans_2^2)*(k2-2*k3)*(s2)^3 - ...
                                             2/Par_Layout.L_trans_2*(k2-2*k3)*(s2)^2 + C1 - Par_Layout.Yaw_trans;
    k2 = double(solve(fun_yaw_trans2b(k2)));
    Par_Layout.R2 = double(1/k2);
    Par_Layout = Cal_fun_Layout_211226_v4(Par_Layout);
end
if strcmp(InpPar.Type_simulation,'Preload') || ~exist('Pre_pos_Radius_Vehicle', 'var')
    pos_Radius_Vehicle = zeros(7,5);      % [各车辆Body里程，第i步和第i-1步时，各车辆Body曲率半径、相对全局坐标系的摇头角]
    pos_Radius_Vehicle(:,2) = -inf;
    pos_Radius_Vehicle(:,4) = -inf;
    pos_Body_global = zeros(7,6);          % [第i步和第i-1步时，各车辆Body在全局坐标系中的X,Y,Z坐标]
    pos_WS_BogieCS = zeros(4,6);
    pos_BG_CarbodyCS = zeros(2,6);
    pos_yaw_track = zeros(7,2);               % [第i步和第i-1步时，各车辆Body相对全局坐标系的摇头角]
else
    pos_Radius_Vehicle = Pre_pos_Radius_Vehicle;
    pos_Body_global = Pre_pos_Body_global;
    pos_WS_BogieCS = Pre_pos_WS_BogieCS;
    pos_BG_CarbodyCS = Pre_pos_BG_CarbodyCS;
    pos_yaw_track = Pre_pos_yaw_track;
end
vel_WS_BogieCS = zeros(4,6);
vel_BG_CarbodyCS = zeros(2,6);
vel_Body_global = repmat([InpPar.Vlc, 0, 0], 7, 1);
vel_yaw_track = zeros(7, 1);


% D2. Track Irregulatiry - TIrr, InpPar.d_TIrr InpPar .Vlc
% TIrr: Mileage (m), Patch-1-Z (m), Patch-1-Y (m), Patch-2-Z (m), Patch-2-Y
% (m), Patch-3-Z (m), Patch-3-Y (m), Patch-4-Z (m), Patch-4-Y (m)......
% D2a. No Track Irr
InpPar.TIrr = zeros(2,9);
InpPar.TIrr(:,1) = [-1000; 1000];
InpPar.d_TIrr = InpPar.TIrr;
InpPar.Test = [];

% D2b. SweptFreq - TIrr
% TIrr: [Mileage, Z_L1, Y_L1, Z_R1, Y_R1, Z_R2, Y_R2, Z_R3, Y_R3]
% [TIrr, InpPar.d_TIrr] = Load_TIrr(InpPar.Vlc, j0, drtaT);

% D2c. TurnoutTIrr - TIrr
dX_TIrr_Spline = 3;
X_TIrr_Simulation_Start = 46;

% 20190806
% filename = 'ChangTuXi_D_20190806_C1_Northbound_v3.txt';
% InpPar = TIrr_WideFreq_v3(InpPar, dX_TIrr_Spline, X_TIrr_Simulation_Start, dX_TIrr, filename);

% filename = 'TIrr_GSDS-Dalianbei-Shenyangbei-07112020-095710-1(280-18)_pic.txt';
% dX_TIrr = 50;
% InpPar = TIrr_WideFreq_v3(InpPar, dX_TIrr_Spline, X_TIrr_Simulation_Start, dX_TIrr, filename);
%%% Sort_temp
% clear Sort_temp
% Sort_temp.TIrr = InpPar.TIrr;
% Sort_temp.d_TIrr = InpPar.d_TIrr;
% Sort_temp.Test = InpPar.Test;
% save Sort_temp.mat Sort_temp
% load Sort_temp.mat
% InpPar.TIrr = Sort_temp.TIrr;
% InpPar.d_TIrr = Sort_temp.d_TIrr;
% InpPar.Test = Sort_temp.Test;

% figure(51); clf
% xx = 0:0.1:120;
% subplot(2,1,1)
% plot(InpPar.TIrr(:,1), InpPar.TIrr(:,2)*1000); hold on
% plot(InpPar.TIrr(:,1), InpPar.TIrr(:,4)*1000); hold on
% % plot(xx, interp1(InpPar.TIrr(:,1), InpPar.TIrr(:,4)*1000, xx, 'spline'), '--'); hold on
% grid on
% set(gca, 'ydir', 'reverse'); xlabel('Mileage (m)'); ylabel('TIrr-Z (mm)');
% subplot(2,1,2)
% plot(InpPar.TIrr(:,1), InpPar.TIrr(:,3)*1000); hold on
% plot(InpPar.TIrr(:,1), InpPar.TIrr(:,5)*1000); hold on
% % plot(xx, interp1(InpPar.TIrr(:,1), InpPar.TIrr(:,3)*1000, xx, 'spline'), '--'); hold on
% grid on
% set(gca, 'ydir', 'reverse'); xlabel('Mileage (m)'); ylabel('TIrr-Y (mm)');

% D2d. WideFreqExt - TIrr
% dX_TIrr_Spline = 4;
% X_TIrr_Simulation_Start = 40;
% % X_TIrr_Measured = [842.870, 843.1+0.1];
% Part_TIrr = 1;
% X_TIrr_Measured = [842.578+70e-3*(Part_TIrr-1), 842.578+75e-3*Part_TIrr];
% InpPar = TIrr_WideFreq_v3(InpPar, dX_TIrr_Spline, X_TIrr_Simulation_Start, X_TIrr_Measured);


% D3. Wheel and Rail Profile
% D3a. Wheel Profile & Con Parameters
WheelPro_ProCS = Radius_wheel(InpPar, Par_Vehicle);

% figure(7); clf
% subplot(2,1,1)
% plot(WheelPro_ProCS.profile_w_R(:,1)-(1.353/2+0.07)*0, WheelPro_ProCS.profile_w_R(:,2));grid on; set(gca,'ydir','reverse');
% title('Right Wheel')
% XRangeLabel = get(gca, 'xlim');
% subplot(2,1,2)
% plot(WheelPro_ProCS.profile_w_R_Radius(:,1)-(1.353/2+0.07)*0, WheelPro_ProCS.profile_w_R_Radius(:,2));grid on
% % plot(WheelPro_ProCS.Con_ang_R(:,1), WheelPro_ProCS.Con_ang_R(:,2));grid on
% xlim(XRangeLabel)

WheelPro_ProCS = Par_Con(WheelPro_ProCS);

% D3b. Rail Profile: Bezier Interpolation
Choose_zgygRaise = 0;           % 翼轨抬高
Choose_zjgUnEven = 0;           % 尖轨降低值超差
if strcmp(InpPar.Choose_Turnout, '07(009)')
    InpPar = Bezier_InterpProfile_210620(InpPar, Choose_Plot, Choose_zgygRaise, Choose_zjgUnEven);
elseif strcmp(InpPar.Choose_Turnout, 'CN18')
    InpPar = Bezier_InterpProfile_CN18_250813(InpPar, Choose_Plot, Choose_zgygRaise, Choose_zjgUnEven);
end

RailPro_ProCS = struct;
if strcmp(InpPar.Choose_Turnout, '07(009)')
    RailPro_ProCS = Get_Profile_P1_Through_210624(InpPar, j1, Par_Vehicle, RailPro_ProCS, {'L1'});               % Turnout
end
% RailPro_ProCS = Get_Profile_P1_Through_210624(InpPar, j1, Par_Vehicle, RailPro_ProCS, {'L1', 'R1'});   % PlainTrack

% E1. OOR
% % 25 阶 14.6 万公里
% InpPar.OOR_A = 10^(14.6/20) * 1e-6;
% InpPar.OOR_NM = 25;
% % 15 阶 23.5 万公里
% InpPar.OOR_A = 10^(18.2/20) * 1e-6;
% InpPar.OOR_NM = 15;
% InpPar.OOR_Phase = -1*InpPar.OOR_NM*(InpPar.Vlc/Par_Vehicle.R0)*(104.304-j0)/InpPar.Vlc;
% if Choose_Plot == 1
%     time = 0 : 1/2e4 : (InpPar.FWc-j0)/InpPar.Vlc;
%     xx = InpPar.Vlc*time+j0;
%     yy = InpPar.OOR_A *sin(InpPar.OOR_NM*(InpPar.Vlc/Par_Vehicle.R0)*time+InpPar.OOR_Phase);
%     figure(99); clf
%     plot(xx, yy);
%     grid on
% end

% Appendix: RailBeam, InpPar
InpPar = Cal_RailBeam_230518(InpPar, Choose_zjgUnEven);
if Choose_Plot==1
%     T2 = 'R1';
%     T2 = 'R2_zgyg';
    T2 = 'R2_zjg'; XLabelRange = [50, 60];
    T2 = 'R3'; XLabelRange = [102.5, 105];

%     figure(98); clf
%     if isfield(InpPar.RailBeam.Win, T2)
%         plot(InpPar.RailBeam.Win.(T2)(:,1), InpPar.RailBeam.Win.(T2)(:,2));
%         xlabel('Mileage (m)'); ylabel('Win');
%         set(gca, 'FontName', 'Times', 'FontSize', 11); grid on
%     end

%     figure(99); clf
%     subplot(2,1,1)
%     plot(InpPar.RailBeam.Pos_Y.(T2)(:,1), InpPar.RailBeam.Pos_Y.(T2)(:,2)); 
%     set(gca, 'ydir', 'reverse');
%     xlabel('Mileage (m)'); ylabel('Pos Y (m)');
%     subplot(2,1,2)
%     plot(InpPar.RailBeam.Vel_Y.(T2)(:,1), InpPar.RailBeam.Vel_Y.(T2)(:,2)); hold on    
%     if isfield(InpPar.RailBeam.Win, T2)
%         Tar_win = InpPar.RailBeam.Win.(T2);
%         win_temp = interp1(Tar_win(:,1), Tar_win(:,2), InpPar.RailBeam.Vel_Y.(T2)(:,1), 'linear');
%         plot(InpPar.RailBeam.Vel_Y.(T2)(:,1), InpPar.RailBeam.Vel_Y.(T2)(:,2).*win_temp); hold on
%     end
% %     plot(InpPar.RailBeam.Vel_Y.R2_zjg_ori(:,1), InpPar.RailBeam.Vel_Y.R2_zjg_ori(:,2)); hold on    
%     xlabel('Mileage (m)'); ylabel('Vel Y (m/s)');

    figure(100); clf
    subplot(2,1,1)
    plot(InpPar.RailBeam.Pos_Z.(T2)(:,1), InpPar.RailBeam.Pos_Z.(T2)(:,2)); 
    set(gca, 'ydir', 'reverse');
    xlabel('Mileage (m)'); ylabel('Pos Z (m)');
    xlim(XLabelRange);
    subplot(2,1,2)
    plot(InpPar.RailBeam.Vel_Z.(T2)(:,1), InpPar.RailBeam.Vel_Z.(T2)(:,2)); hold on
    xlabel('Mileage (m)'); ylabel('Vel Z (m/s)');
    
    for kk = 1:1:2
        subplot(2,1,kk)
        set(gca, 'FontName', 'Times', 'FontSize', 11); grid on;
        xlim(XLabelRange);
    end
end

% D4. Figure Plot
Fig_num_max = 4;
Fig_pos_times = 0.8*0;
PlotHandles = PlotHandles_Control(InpPar, j0, Fig_num_max, Fig_pos_times, Choose_Screen);

% D5. CPU Time
if ~exist('hwait', 'var')
    hwait = waitbar(0,'Progress = 0%');
end
h = figure(2);
pic = get(h, 'Position');
set(hwait, 'Units', 'centimeters', 'Position', [pic(1), pic(2)-2.8, 9.65, 2]);


%% ===================== Start Iteration: STEP xlcs
if xlcs==xlcs_start
    IntStep = j1;
    IntStep_End = InpPar.FWc;
    xcs_PreviousStep = 0;
    xcs_PreviousStep_All = 0;
    Error_PreviousStep = [0,0];
end

% while IntStep <= IntStep_End  % Face
% while IntStep > IntStep_End         % Trail
if strcmp(InpPar.VehicleDir, 'Face')
    IntStep_Flag = (IntStep <= IntStep_End);
elseif strcmp(InpPar.VehicleDir, 'Trail')
    IntStep_Flag = (IntStep > IntStep_End);
end
while IntStep_Flag==1
      
    % Initialization
    ZP_IntError_Nor(1,xlcs) = 1;
    ZP_IntError_NorTan(1,xlcs) = 1;
    mod_t = Set_mod_t(InpPar, j1, xlcs);
    if strcmp(InpPar.Type_simulation, 'Preload') && xlcs>3
        Newmark = struct;
    end
    
%     T = ZP_Dyn.T(end,1);
    T_VTS_ori = T;
    j1_VTS_ori = j1;
    times_drtaT = 1;
    if max( abs(diff(drtaT_His)) ) > 0
        i_drtaT = i_drtaT_PreviousStep;
    else
        i_drtaT = i_drtaT_PreviousStep-1+1*(i_drtaT_PreviousStep==1);
%         i_drtaT = i_drtaT_PreviousStep-1+1*(i_drtaT_PreviousStep==2);
    end

    Pos_WS = j1-Par_Vehicle.Distance_Vehicle;
    bools_1 = (Pos_WS >= 60) & (Pos_WS <104); 
    if ~isempty(find(bools_1, 1)) && i_drtaT<2
        i_drtaT = 2;
    end
    bools_2 = (Pos_WS >= 104) & (Pos_WS <105); 
    if ~isempty(find(bools_2, 1)) && i_drtaT<3
        i_drtaT = 3;
    end

    clc
    if m1>1
        toc
    end
    disp(['Int. Steps = ', num2str(xlcs)]);
    disp(['Int. Times = ', num2str(xcs_PreviousStep), ' / ', num2str(xcs_PreviousStep_All)]);
    disp(['Int. Error = ', num2str(Error_PreviousStep(1)*100), '% / ', num2str(Error_PreviousStep(2)*100), '%']);
    tic
    % ===================== Start Iteration: i_drtaT
    while i_drtaT<=length(Range_drtaT)
        % drtaT, T, j1, xcs
        xcs = 1;
        drtaT = Range_drtaT(i_drtaT);
        drtaT_His(:,end) = drtaT;
        T = T_VTS_ori+drtaT;
        j1 = j1_VTS_ori + InpPar.Vlc*drtaT;
        rate = 100*(j1-j0)/(InpPar.FWc-j0);
        
        % 修正因迭代不收敛造成的 Con_WS 紊乱, ZP_Dyn
        Con_Int = Define_Con_Int(InpPar);
        if times_drtaT>1
            ZP_IntError_Nor(:,xlcs) = [1; zeros(length(ZP_IntError_Nor(:,xlcs))-1,1)];
            ZP_IntError_NorTan(:,xlcs) = [1; zeros(length(ZP_IntError_NorTan(:,xlcs))-1,1)];
            Prhxf = zeros(N_Patch_sum,6);                          % 左右车轮编号及X、Y、Z三方向轮轨间蠕滑力（行）修正值分量，列代表蠕滑力和蠕滑力矩
            Pjcc = zeros(N_Patch_sum,1);                           % 法向接触力垂向分量
            Pjch = zeros(N_Patch_sum,1);                           % 法向接触力横向分量
            for i1 = 1:1:InpPar.Nw
                T1 = InpPar.Exp_WS{i1};
                for i2 = 1:1:length(InpPar.Type_Side)
                    T2 = InpPar.Type_Side{i2};
                    for kk = 1:1:length(ZP_Dyn.Normal_Force.(T2)(i1,:))
                        if size(ZP_Dyn.Normal_Force.(T2){i1,kk},1)==xlcs
                            Con_WS.(T1).Normal_Force.(T2)(kk,:) = ZP_Dyn.Normal_Force.(T2){i1,kk}(xlcs,2:end);
                            Con_WS.(T1).Prhxf_T.(T2)(kk,:) = ZP_Dyn.Prhxf.(T2){i1,kk}(xlcs,2:end);
                            Con_WS.(T1).Con_wheel_2.(T2)(kk,:) = ZP_Dyn.Con_Wheel_2.(T2){i1,kk}(xlcs,2:end-1);
                            if InpPar.NM_FW>0
                                Con_WS.(T1).ShapeFun_FW.(T2).XOY{kk,1} = ZP_Dyn.ShapeFun_FW.(T2).XOY{i1,kk}(xlcs,2:end);
                                Con_WS.(T1).ShapeFun_FW.(T2).Z{kk,1} = ZP_Dyn.ShapeFun_FW.(T2).Z{i1,kk}(xlcs,2:end);
                                Con_WS.(T1).DOF_pos_FW.(T2).Node_Around_XOY{kk,1} = reshape(ZP_Dyn.DOF_pos_FW.(T2).Node_Around_XOY{i1,kk}(xlcs,2:end)',4,3);
                                Con_WS.(T1).DOF_pos_FW.(T2).Node_Around_Z{kk,1} = reshape(ZP_Dyn.DOF_pos_FW.(T2).Node_Around_Z{i1,kk}(xlcs,2:end)',2,3);
                            end
                            i_Patch = ZP_Dyn.Normal_Force.(T2){i1,kk}(xlcs,5);
                            pos = (i1-1)*InpPar.N_ConPatch+i_Patch;
                            Pjch(pos,1) = Pjch(pos,1) + ZP_Dyn.Normal_Force.(T2){i1,kk}(xlcs,3);
                            Pjcc(pos,1) = Pjcc(pos,1) + ZP_Dyn.Normal_Force.(T2){i1,kk}(xlcs,4);
                            Prhxf(pos,:) = Prhxf(pos,:) + ZP_Dyn.Prhxf.(T2){i1,kk}(xlcs,2:end);
                        end
                    end
                end
            end
        else
            xcs_PreviousStep_All = 0;
        end
        
        % ZP_Dis
        if (strcmp(InpPar.Type_simulation, 'Preload') && xlcs>6 && max(abs(diff(drtaT_His)))>0) || ...
           (strcmp(InpPar.Type_simulation, 'Cal') && max(abs(diff(drtaT_His)))>0) || times_drtaT>1
            x_t = ZP_Dyn.T(:,1);
            xx_t = T_VTS_ori-drtaT*2 : drtaT: T_VTS_ori ;
            if min(xx_t)>=min(x_t)
                Zwy(:,1:3) = interp1(x_t, ZP_Dis(1:xlcs,:), xx_t', 'linear')';
                Zsd(:,1:3) = interp1(x_t, ZP_Vel(1:xlcs,:), xx_t', 'linear')';
                Zjsd(:,1:3) = interp1(x_t, ZP_Acc(1:xlcs,:), xx_t', 'linear')';
                Zwy(:,4) = Zwy(:,3);
                Zsd(:,4) = Zsd(:,3);
                Zjsd(:,4) = Zjsd(:,3);
            else
                i_drtaT = i_drtaT+1;
                drtaT = Range_drtaT(i_drtaT);
                drtaT_His(:,end) = drtaT;
                T = T_VTS_ori+drtaT;
                j1 = j1_VTS_ori + InpPar.Vlc*drtaT;
                rate = 100*(j1-j0)/(InpPar.FWc-j0);
            end
        end
        
        % DISP
        disp(['====== VTS Order: ', num2str(times_drtaT), ' ======']);
        disp(['Int. Time = ', num2str(T), 's']);
        disp(['Mileage = ', num2str(fix((j1-(Par_Vehicle.Ll1+Par_Vehicle.Ll2)*2*sign(strcmp(InpPar.VehicleDir, 'Trail')))*1000)/1000), 'm']);
        disp(['Specific TS = ', num2str(drtaT), 's']);
        waitbar(rate/100,hwait,['Mileage = ', num2str(fix((j1-(Par_Vehicle.Ll1+Par_Vehicle.Ll2)*2*sign(strcmp(InpPar.VehicleDir, 'Trail')))*1000)/1000), ...
                      'm; Steps = ', num2str(xlcs), '; Progress = ' num2str(fix(rate*100)/100) '%']);
        
        % RailPro_ProCS
        RailPro_ProCS.R1 = struct;
        RailPro_ProCS.R2 = struct;
        RailPro_ProCS.R3 = struct;
        if strcmp(InpPar.Choose_Turnout, '07(009)')
            RailPro_ProCS = Get_Profile_P1_Through_210624(InpPar, j1, Par_Vehicle, RailPro_ProCS, {'R1', 'R2', 'R3'});
        elseif strcmp(InpPar.Choose_Turnout, 'CN18')
            RailPro_ProCS.L1 = struct;
            RailPro_ProCS = Get_Profile_P1_Through_CN18_250813(InpPar, j1, Par_Vehicle, RailPro_ProCS, {'L1', 'R1', 'R2', 'R3'});
        end

        if Choose_Plot==1
            figure(11); clf
            T2 = 'R3';
            if ~isempty(RailPro_ProCS.(T2).FF_Profile)
                subplot(2,1,1)
                if strcmp(InpPar.VehicleDir, 'Face')
                    TP = 'FF';
                else
                    TP = 'RR';
                end
                plot(RailPro_ProCS.(T2).([TP, '_Profile'])(:,1)*1000, RailPro_ProCS.(T2).([TP, '_Profile'])(:,2)*1000);  hold on
                plot(RailPro_ProCS.(T2).([TP, '_FrontProfile'])(:,1)*1000, RailPro_ProCS.(T2).([TP, '_FrontProfile'])(:,2)*1000, '--');  hold on
                plot(RailPro_ProCS.(T2).([TP, '_RearProfile'])(:,1)*1000, RailPro_ProCS.(T2).([TP, '_RearProfile'])(:,2)*1000, '--');  hold on
                set(gca,'ydir','reverse');  grid on;
                title(T2);
                subplot(2,1,2)
                plot(RailPro_ProCS.(T2).([TP, '_Radius'])(:,1)*1000, RailPro_ProCS.(T2).([TP, '_Radius'])(:,2)*1000);
                ylim([0,500]);  grid on;
            end
        end
        
        % Shape Functions
        clear ShapeFunction RailBeam_Motion
        [ShapeFunction, RailBeam_Motion] = Cal_ShapeFunction_Beam188_FWV(InpPar, Par_Vehicle, j1);

        % ===================== Start Iteration: xcs
        while (xcs<=2) || ( xcs<=xcs_t_limit_3 && (ZP_IntError_Nor(xcs,xlcs)>Tolerance_Int_3||ZP_IntError_NorTan(xcs,xlcs)>Tolerance_Int_3) && ...
                  (isempty(find(diff(ZP_IntError_Nor(2:end,xlcs))>0,1))&&isempty(find(diff(ZP_IntError_NorTan(2:end,xlcs))>0,1)))  )
%         while (xcs<=2) || ( xcs<=xcs_t_limit_3 && (ZP_IntError_Nor(xcs,xlcs)>Tolerance_Int_3||ZP_IntError_NorTan(xcs,xlcs)>Tolerance_Int_3) )
               
            % ===================== DamperNL
            if strcmp(InpPar.Type_Vehicle, 'CRH380A_v6')
                [DamperNL, Cxt, Newmark, Park, Houbolt] = Judge_DamperNL(InpPar, xcs, xlcs, Par_Vehicle, Zwy, Zsd, ...
                    vel_yaw_track, Mxt, Kxt, Cxt, drtaT, i_drtaT, Newmark, Park, Houbolt, C_vehicle_v0, Con_Int, Par_FW);
            elseif strcmp(InpPar.Type_Vehicle, 'CR400AF') || strcmp(InpPar.Type_Vehicle, 'CR400BF')
                [DamperNL, Cxt, Newmark, Park, Houbolt] = Judge_DamperNL_CR400AF(InpPar, xcs, xlcs, Par_Vehicle, Zwy, Zsd, ...
                    vel_yaw_track, Mxt, Kxt, Cxt, drtaT, i_drtaT, Newmark, Park, Houbolt, C_vehicle_v0, Con_Int, Par_FW);
            end
         
            % ===================== Gravity
            Pxt = zeros(DOF_sum,1);         % 荷载列阵（单列，位移变分为行）
            Pxt = Pxt + Pxt_Gravity;
            
            % ===================== 曲线轨道离心力和坐标变换对车辆系统做功
            if ~strcmp(InpPar.Type_Layout,'Straight')
                [pos_Radius_Vehicle, pos_Body_global, pos_WS_BogieCS, pos_BG_CarbodyCS, vel_WS_BogieCS, vel_BG_CarbodyCS, ...
                 pos_yaw_track, vel_Body_global, vel_yaw_track, Pxt] = ...
                External_Force_Curve_210227_v4(InpPar, Par_Vehicle, j1, Par_Layout, pos_Radius_Vehicle, pos_Body_global, pos_WS_BogieCS, pos_BG_CarbodyCS, pos_yaw_track, Zsd, Pxt);
            end
            
            % ===================== 非线性阻尼力元对车辆系统做功
            if strcmp(InpPar.Type_Vehicle, 'CRH380A') || strcmp(InpPar.Type_Vehicle, 'CRH380A_v2') 
                [Pxt, FZ_PS_Damp, FX_SS_Damp, FY_SS_Damp] = NonLinear_DampingForce(InpPar, Par_Vehicle, vel_yaw_track, vel_BG_CarbodyCS, Zsd, Pxt);
            elseif strcmp(InpPar.Type_Vehicle, 'CRH380A_v3')
                [Pxt, FZ_DPz_Damp, FX_Sx_Damp, FY_DPy_Damp, dy_SS] = NonLinear_DampingForce_v3(vel_yaw_track, vel_BG_CarbodyCS, Zsd, Pxt, DamperNL);
            elseif strcmp(InpPar.Type_Vehicle, 'CR400AF') || strcmp(InpPar.Type_Vehicle, 'CR400BF')
                [Pxt, DamperNL] = NonLinear_DampingForce_CR400AF(InpPar, Par_Vehicle, xlcs, Pxt, DamperNL);
            else
                [Pxt, DamperNL] = NonLinear_DampingForce_v4Re(InpPar, Par_Vehicle, xlcs, Pxt, DamperNL);
            end
            
            % ===================== 轮轨力对车辆系统做功
            [Pxt, Q_temp] = WR_Force_VehicleSys_RotationIII(InpPar, Par_Vehicle, Par_Track, Par_FW, Pxt, Zwy, Pjcc, Pjch, Prhxf, Con_WS);

            % ===================== 轮轨力对轨道系统做功
            if strcmp(InpPar.Type_Track,'Co-Running')
                Pxt = WR_Force_RT(Pxt, Pjcc, Pjch, Prhxf);
            elseif strcmp(InpPar.Type_Track, 'FT-Modal')
                [Pxt, Pxt_Track] = WR_Force_ModalFT(InpPar, xlcs, Pxt, Pjcc, Pjch, Prhxf, Con_WS, ShapeFunction);
            elseif strcmp(InpPar.Type_Track, 'FT-FEM')
                Pxt = WR_Force_FT_FEM(Pxt, Pjcc, Pjch, Prhxf, Con_WS, ShapeFunction);
            end
            
            % ===================== 动力响应计算
            [Zwy, Zsd, Zjsd] = Integration_Park(InpPar, xlcs, m1, Mxt, Kxt, Cxt{2,1}, Pxt, Zwy, Zsd, Zjsd, drtaT, i_drtaT, Con_WS, Newmark, Park, Houbolt);
            
            % ===================== Dis_Rail Vel_Rail Acc_Rail 钢轨位移、速度、加速度
            if strcmp(InpPar.Type_Track,'Co-Running')
                [Dis_Rail, Vel_Rail, Acc_Rail] = RailDyn_RT(Zwy, Zsd, Zjsd);
            elseif strcmp(InpPar.Type_Track, 'FT-Modal')
                [Dis_Rail, Vel_Rail, Acc_Rail, DynStatus_Rail] = RailDyn_ModalFT(InpPar, Zwy, Zsd, Zjsd, ShapeFunction);
            elseif strcmp(InpPar.Type_Track, 'FT-FEM')
                [Dis_Rail, Vel_Rail, Acc_Rail, DynStatus_Rail] = RailDyn_FT_FEM(Zwy, Zsd, Zjsd, ShapeFunction);
            end
            
            % Con_Int(xcs,:)
            for i1 = 1:1:InpPar.Nw
                for i2 = 1:1:InpPar.N_ConPatch
                    T1 = [InpPar.Exp_WS{i1},'_',InpPar.Exp_DummyRail{i2}];
                    Con_Int.Dis_Rail.(T1)(xcs,:) = Dis_Rail(InpPar.N_ConPatch*(i1-1)+i2,:);
                    Con_Int.Vel_Rail.(T1)(xcs,:) = Vel_Rail(InpPar.N_ConPatch*(i1-1)+i2,:);
                    Con_Int.Acc_Rail.(T1)(xcs,:) = Acc_Rail(InpPar.N_ConPatch*(i1-1)+i2,:);
                end
            end
            Con_Int.Zwy(xcs,:) = Zwy(:,4)';
            Con_Int.Zsd(xcs,:) = Zsd(:,4)';
            Con_Int.Zjsd(xcs,:) = Zjsd(:,4)';
            Con_Int.Pxt(xcs,:) = Pxt(:,1)';
            
            % ===================== Multi_Point_Contact
            if ~exist('d0', 'var') % 未修改
                [d0, Dis_min_L, Dis_min_R] = Cal_d0_FW(InpPar, Par_Vehicle, Par_Track, Par_FW, WheelPro_ProCS, Zwy, RailPro_ProCS);
            end
            Pjc(:,1)  = Pjc(:,2);
            Pjc(:,2) = zeros(N_Patch_sum,1);
            Pjcc = zeros(N_Patch_sum,1);
            Pjch = zeros(N_Patch_sum,1);
            Prhx = zeros(N_Patch_sum,3);
            Prhxf = zeros(N_Patch_sum,6);
            
            for i11 = 1:1:InpPar.Nw
%                 [Mileage, Con_str, Pjc, Pjch, Pjcc, Prhx, Prhxf] = Multi_Con_230412_FW_IVb3(InpPar, Par_Vehicle, Par_Track, Par_FW, WheelPro_ProCS, ZP_Con, ZP_Dyn, j1, xlcs, ...
%                  i11, Zwy, Zsd, Dis_Rail, Vel_Rail, d0, Pjc, Pjch, Pjcc, Prhx, Prhxf, RailPro_ProCS,...
%                  pos_Radius_Vehicle, pos_Body_global, vel_Body_global, vel_yaw_track, drtaT, RailBeam_Motion, dX_TIrr_Spline, X_TIrr_Simulation_Start);

                [Mileage, Con_str, Pjc, Pjch, Pjcc, Prhx, Prhxf] = Multi_Con_250812(InpPar, Par_Vehicle, Par_Track, Par_FW, WheelPro_ProCS, ZP_Con, ZP_Dyn, j1, xlcs, ...
                 i11, Zwy, Zsd, Dis_Rail, Vel_Rail, d0, Pjc, Pjch, Pjcc, Prhx, Prhxf, RailPro_ProCS,...
                 pos_Radius_Vehicle, pos_Body_global, vel_Body_global, vel_yaw_track, drtaT, RailBeam_Motion, dX_TIrr_Spline, X_TIrr_Simulation_Start);
                
                % WR_Geometry = [Roll_DWR, Yaw_DWR, Yw_DWR, Zw_DWR, Roll_DWL, Yaw_DWL, Yw_DWL, Zw_DWL];
                % 保存第 xcs 迭代分步的计算结果
                Con_WS.(InpPar.Exp_WS{i11}) = Con_str;
                Con_Int = Storage_Iteration_P1_220713(InpPar, Con_Int, Con_str, i11, xcs, Mileage, DamperNL);
            end
            
            % ===================== 迭代误差分析
            % 求前后两步，左右两侧法向接触力计算误差
            temp_P_Nor = abs((Pjc(:,2)-Pjc(:,1))./Pjc(:,2));
            bools = ~isnan(temp_P_Nor);
            if ~isempty(temp_P_Nor(bools,:))
                IntError_Nor_max = max(temp_P_Nor(bools,:));
            else
                IntError_Nor_max = 0;
            end
            
            % 求前后两步，每一个接触对蠕滑力和法向接触力合力计算误差(Cal)
            P_WRForceError(:,1:3) = P_WRForceError(:,4:6);
            P_WRForceError(:,4:6) = [zeros(N_Patch_sum,1) Pjch(:,1) Pjcc(:,1)] + Prhxf(:,1:3);
            P_NorTan(:,1) = (P_WRForceError(:,1).^2+P_WRForceError(:,2).^2+P_WRForceError(:,3).^2).^0.5;
            P_NorTan(:,2) = (P_WRForceError(:,4).^2+P_WRForceError(:,5).^2+P_WRForceError(:,6).^2).^0.5;
            temp_P_NorTan = abs((P_NorTan(:,2)-P_NorTan(:,1))./P_NorTan(:,2));
            bools = ~isnan(temp_P_NorTan);
            if ~isempty(temp_P_NorTan(bools,:))
                IntError_NorTan_max = max(temp_P_NorTan(bools,:));
            else
                IntError_NorTan_max = 0;
            end
            
            % 积分误差统计：列为积分步xlcs，行为每一积分步迭代次数
            ZP_IntError_Nor(xcs+1,xlcs) = IntError_Nor_max;
            ZP_IntError_NorTan(xcs+1,xlcs) = IntError_NorTan_max;
            
            % 存储迭代不平衡项 ZP_Int
            % ZP_Int.Zwy：积分步、导向轮对里程、drtaT、位移、速度、加速度、荷载、法向力迭代误差、法向力切向力合力迭代误差、模态叠加前轮对节点的荷载矩阵
            if  (xcs==xcs_t_limit_3 && (ZP_IntError_Nor(xcs,xlcs)>=Tolerance_Int_3||ZP_IntError_NorTan(xcs,xlcs)>=Tolerance_Int_3)) || ...
              ~(isempty(find(diff(ZP_IntError_Nor(2:end,xlcs))>0,1))&&isempty(find(diff(ZP_IntError_NorTan(2:end,xlcs))>0,1)))
                ZP_Int = Storage_Iteration_P2_220713(InpPar, ZP_Int, xlcs, j1, xcs_t, Con_Int, Q_temp, ZP_IntError_Nor, ZP_IntError_NorTan, drtaT);
                xcs_t = xcs_t+1;
            end
            
            m1 = m1+1;                        % 所有积分步迭代总次数
            xcs = xcs+1;                      % 第xlcs积分步下迭代次数
        end                                   % ============================  完成第xlcs积分步的校正/预测
        disp(['Specific TS-Int. Times = ', num2str(xcs-1)]);
        disp(['Specific TS-Int. Error = ', num2str(IntError_Nor_max*100), '% / ', num2str(IntError_NorTan_max*100), '%']);
        xcs_PreviousStep = xcs-1;
        xcs_PreviousStep_All = xcs_PreviousStep_All+xcs_PreviousStep;
        Error_PreviousStep = [IntError_Nor_max, IntError_NorTan_max];
        
        if ZP_IntError_Nor(xcs,xlcs)<=Tolerance_Int_2 && ZP_IntError_NorTan(xcs,xlcs)<=Tolerance_Int_2
%         if ZP_IntError_Nor(xcs,xlcs)<=Tolerance_Int_3 && ZP_IntError_NorTan(xcs,xlcs)<=Tolerance_Int_3
            i_drtaT_PreviousStep = i_drtaT;
            break
        else
            i_drtaT = i_drtaT+1;
            times_drtaT = times_drtaT+1;
        end

    end                                       % ============================  完成第 i_drtaT 积分步的计算    

    % ===================== 迭代不收敛 预警
    if  i_drtaT>length(Range_drtaT)
        temp = input('Warnings: Int. Error > 1% ');
    end
       
    % ===================== 输出结果-1
%     [ZP_Dyn, ZP_Con] = Output_ZP_FW_220713(InpPar, ZP_Dyn, ZP_Con, xlcs, Par_Track, Con_WS, Zwy, Pjcc, Pjch, Prhxf, Dis_Rail, Vel_Rail, Acc_Rail, RailPro_ProCS, drtaT, i_drtaT, times_drtaT, T, DamperNL);
    [ZP_Dyn, ZP_Con] = Output_ZP_FW_230517(InpPar, ZP_Dyn, ZP_Con, xlcs, Par_Track, Con_WS, Zwy, Pjcc, Pjch, Prhxf, Dis_Rail, Vel_Rail, Acc_Rail, RailPro_ProCS, drtaT, i_drtaT, times_drtaT, T, DamperNL);
    
    % ===================== 输出结果-2: ZP_Dis, ZP_Vel, ZP_Acc, ZP_Load
    % (Cal)
    ZP_Dis(1+xlcs,:) = Zwy(:,4);
    ZP_Vel(1+xlcs,:) = Zsd(:,4);
    ZP_Acc(1+xlcs,:) = Zjsd(:,4);
    ZP_Load(1+xlcs,:) = Pxt;
    ZP_NF(:,1+xlcs) = Pjc(:,2);
    % 对应的曲率半径
    if ~strcmp(InpPar.Type_Layout, 'Straight')
        ZP_Radius.Radius_Vehicle{1+xlcs,1} = pos_Radius_Vehicle;
        ZP_Radius.pos_Body_global{1+xlcs,1} = pos_Body_global;
        ZP_Radius.pos_WS_BogieCS{1+xlcs,1} = pos_WS_BogieCS;
        ZP_Radius.pos_BG_CarbodyCS{1+xlcs,1} = pos_BG_CarbodyCS;
        ZP_Radius.pos_yaw_track{1+xlcs,1} = pos_yaw_track;
        ZP_Radius.vel_yaw_track{1+xlcs,1} = vel_yaw_track;
        ZP_Radius.vel_Body_global{1+xlcs,1} = vel_Body_global;
    end
    
    % 结果前移
    if strcmp(InpPar.Type_simulation,'Cal') || (strcmp(InpPar.Type_simulation,'Preload') && xlcs>=3) ||  (strcmp(InpPar.Type_simulation,'Preload') && exist('Pre', 'var'))
        Zwy(:,1:3) = Zwy(:,2:4);
        Zsd(:,1:3) = Zsd(:,2:4);
        Zjsd(:,1:3) = Zjsd(:,2:4);
        if ~strcmp(InpPar.Type_Layout, 'Straight')
            pos_Radius_Vehicle(:,4:5) = pos_Radius_Vehicle(:,2:3);
            pos_Body_global(:,4:6) = pos_Body_global(:,1:3);
            pos_WS_BogieCS(:,4:6) = pos_WS_BogieCS(:,1:3);
            pos_BG_CarbodyCS(:,4:6) = pos_BG_CarbodyCS(:,1:3);
            pos_yaw_track(:,2) = pos_yaw_track(:,1);
        end
    end
    drtaT_His(:,1:end-1) = drtaT_His(:,2:end);
    
    xlcs = xlcs + 1;                        % 第xlcs积分步
    
    % ===================== 实时绘图表示结果
    if mod(xlcs,mod_t)==0 && xlcs>5
        if strcmp(InpPar.VehicleDir, 'Face')
            T1 = 'FF';
        elseif strcmp(InpPar.VehicleDir, 'Trail')
            T1 = 'RF';
%             T1 = 'RR';
        end
        Plot_Con(PlotHandles.Fig_1, Con_WS.(T1), Par_Vehicle.R0)
        PlotPost(InpPar, ZP_Dyn, ZP_Con, xlcs, DynStatus_Rail, ZP_Dis, ZP_Vel, ZP_Acc, PlotHandles, Fig_num_max, Par_Vehicle, j1, j0, (T1))
    end
    
    % ===================== 计算输出 - Pre
    if k_save<=length(Save_Mileage_Range) && Choose_Save==1
        tt = j1;
        if strcmp(InpPar.VehicleDir, 'Face')
            Save_Flag = (tt > Save_Mileage_Range(k_save));
        elseif strcmp(InpPar.VehicleDir, 'Trail')
            Save_Flag = (k_save>0 && tt < Save_Mileage_Range(k_save));
        end
        if Save_Flag
            clear Pre
            Pre.drtaT = drtaT;               Pre.d0 = d0;                         Pre.j1 = j1;
            Pre.Pjcc = Pjcc;                    Pre.Pjch = Pjch;                    Pre.Prhxf = Prhxf;
            Pre.Zwy = Zwy(:,1:3);          Pre.Zsd = Zsd(:,1:3);            Pre.Zjsd = Zjsd(:,1:3);
            Pre.NF = ZP_NF(:,(xlcs-2):xlcs);                    Pre.Con_WS = Con_WS;
            Pre.pos_Radius_Vehicle = pos_Radius_Vehicle;
            Pre.pos_Body_global = pos_Body_global;
            Pre.pos_WS_BogieCS = pos_WS_BogieCS;
            Pre.pos_BG_CarbodyCS = pos_BG_CarbodyCS;
            Pre.pos_yaw_track = pos_yaw_track;
            Pre.drtaT_His = drtaT_His;
            for i2 = 1:1:InpPar.N_ConPatch
                T2 = InpPar.Exp_DummyRail{i2};
                Source = ZP_Con.RelVel_max.(T2);
                for m = 1:1:size(Source,1)
                    for n = 1:1:size(Source,2)
                        if ~isempty(Source{m,n}) && size(Source{m,n},1)==xlcs
                            Pre.ZP_Con.RelVel_max.(T2){m,n} = Source{m,n}(xlcs,:);
                        end
                    end
                end
            end
            if xlcs>120
                tt = 100;
            else
                tt = xlcs-5;
            end
            Pre.ZP_T = ZP_Dyn.T(end-tt:end,:);
            Pre.ZP_Dis = ZP_Dis(xlcs-tt+1:xlcs,:);
            Pre.ZP_Vel = ZP_Vel(xlcs-tt+1:xlcs,:);
            Pre.ZP_Acc = ZP_Acc(xlcs-tt+1:xlcs,:);
            Pre.ZP_Load = ZP_Load(xlcs-tt+1:xlcs,:);
            eval(['save Pre_CRH380A_009_Face_V350_zgygPf2_', Save_Mileage_Name{k_save}, '.mat Pre'])
            if strcmp(InpPar.VehicleDir, 'Face')
                k_save = k_save + 1;
            elseif strcmp(InpPar.VehicleDir, 'Trail')
                k_save = k_save - 1;
            end
        end
    end
    IntStep = j1;
    if strcmp(InpPar.VehicleDir, 'Face')
        IntStep_Flag = (IntStep <= IntStep_End);
    elseif strcmp(InpPar.VehicleDir, 'Trail')
        IntStep_Flag = (IntStep > IntStep_End);
    end
    
end     % 完成第xlcs步迭代

% Save, Cxt, Park
if kk_Cal==2
    clear ZP_Int
    Cxt{2,1} = [];
    Park .Ajz(2:4,:) = [];
    for i = 2:1:size(Park.Ajz,2)
        Park.Ajz{1,i} = [];
    end
        save CRH380A_009_Face_V350_zgygPf2.mat
end

end

