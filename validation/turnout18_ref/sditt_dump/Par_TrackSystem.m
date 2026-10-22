%% 输出初始参数
function Par_Track = Par_TrackSystem(InpPar)

% global InpPar.Type_Track

clear Par_Track

if strcmp(InpPar.Type_Track,'FT-Modal') || strcmp(InpPar.Type_Track,'FT-FEM') || strcmp(InpPar.Type_Track,'Co-Running')
    % RailPad - Plain Track
    Par_Track.ConsPar_RailPad.Stiff_X = 20e6;
    Par_Track.ConsPar_RailPad.Stiff_Y = 20e6;
    Par_Track.ConsPar_RailPad.Stiff_Z = 25e6;
    Par_Track.ConsPar_RailPad.Damp_X = 20e3;
    Par_Track.ConsPar_RailPad.Damp_Y = 20e3;
    Par_Track.ConsPar_RailPad.Damp_Z = 20e3;
    
    % RailPad - Turnout
%     Par_Track.ConsPar_RailPad.Stiff_X = 20e6;
%     Par_Track.ConsPar_RailPad.Stiff_Y = 20e6;
%     Par_Track.ConsPar_RailPad.Stiff_Z = 275e6;
%     Par_Track.ConsPar_RailPad.Damp_X = 20e3;
%     Par_Track.ConsPar_RailPad.Damp_Y = 20e3;
%     Par_Track.ConsPar_RailPad.Damp_Z = 0;
    
    % RailPad on Baseplate - Turnout
%     Par_Track.ConsPar_Baseplate = Par_Track.ConsPar_RailPad;
%     Par_Track.ConsPar_Baseplate.Stiff_Z = 2000e6;

    % PlatePad - Turnout
% %     Par_Track.ConsPar_PlatePad.Stiff_Z = 27.5e6;
% %     Par_Track.ConsPar_PlatePad.Damp_Z = 20e3;
%     Par_Track.ConsPar_PlatePad.Baseplate_L_Switch.Stiff_Z = load('Baseplate_L_Switch_Stiff_211109.txt');
%     Par_Track.ConsPar_PlatePad.Baseplate_L_Switch.Damp_Z = load('Baseplate_L_Switch_Damp_211109.txt');
%     Par_Track.ConsPar_PlatePad.Baseplate_R_Switch.Stiff_Z = load('Baseplate_R_Switch_Stiff_211109.txt');
%     Par_Track.ConsPar_PlatePad.Baseplate_R_Switch.Damp_Z = load('Baseplate_R_Switch_Damp_211109.txt');

    % Lat Contact - Turnout
%     Par_Track.ConsPar_LatCon.Stiff_X = 0;
%     Par_Track.ConsPar_LatCon.Stiff_Y = 50e6;
%     Par_Track.ConsPar_LatCon.Stiff_Z = 0;
%     Par_Track.ConsPar_LatCon.Damp_X = 0;
%     Par_Track.ConsPar_LatCon.Damp_Y = 0;
%     Par_Track.ConsPar_LatCon.Damp_Z = 0;
       
    Par_Track.fr = 0.40;                  % 钢轨摩擦系数
%     Par_Track.fr = 0.35;                  % 钢轨摩擦系数
%     Par_Track.fr = 0.25;                  % 钢轨摩擦系数
    Par_Track.Er = 214e9;                 % 钢轨弹性模量
    Par_Track.Vr = 0.3;                   % 钢轨泊松比
    Par_Track.Gr = Par_Track.Er/2/(1+Par_Track.Vr);     % 钢轨剪切模量
    Par_Track.Ori_prr = 0.0355;
    Par_Track.Br = 0.7175;                % 两股钢轨工作边的中心距之半
    
    % Rayleigh Damping
    Par_Track.Rayleigh_Alpha = 0;
    Par_Track.Rayleigh_Beta  = 0;
%     Par_Track.Rayleigh_Beta  = 1e-4;

    % SIMPACK ftr. file's parameters
%     Par_Track.Rayleigh_Alpha = 1e-3;
%     Par_Track.Rayleigh_Beta  = 5e-3;
    
elseif strcmp(InpPar.Type_Track,'Co-Running_Benchmark')
    % Benchmark Co-running
    Par_Track.Mr1 = 60;
    Par_Track.Mr2 = 60;
    Par_Track.Mr3 = 60;
    Par_Track.Mr4 = 60;
    Par_Track.Ms = 1400;                  % 轨枕质量（标准轨枕）  kg
    Par_Track.Jt = 450;                   % 轨枕侧滚惯量  kg.m^2
    
    %%% 扣件垂向刚度、阻尼
    Par_Track.Krz1 = 150e6;
    Par_Track.Crz1 = 100e3;
    % Par_Track.Krz2 = 1e6;
    % Par_Track.Crz2 = 1e3;
    Par_Track.Krz2 = 150e6;
    Par_Track.Crz2 = 100e3;
    Par_Track.Krz3 = 150e6;
    Par_Track.Crz3 = 100e3;
    Par_Track.Krz4 = 150e6;
    Par_Track.Crz4 = 100e3;
    %%% 扣件横向刚度、阻尼
    Par_Track.Kry1 = 30e6;
    Par_Track.Cry1 = 150e3;
    % Par_Track.Kry2 = 1e6;
    % Par_Track.Cry2 = 1e3;
    Par_Track.Kry2 = 30e6;
    Par_Track.Cry2 = 150e3;
    Par_Track.Kry3 = 30e6;
    Par_Track.Cry3 = 150e3;
    Par_Track.Kry4 = 30e6;
    Par_Track.Cry4 = 150e3;
    %%% 轨枕刚度和阻尼
    Par_Track.Lt = 0.75;                    % 轨下基础弹簧横向距离
    Par_Track.Kzs = 140e+6;                 % 道床和路基的垂向刚度  N/m
    Par_Track.Czs = 1400e+3;                % 道床和路基的垂向阻尼  N.s/m
    Par_Track.Kys = 1*70e+6;                % 道床的横向刚度  N/m
    Par_Track.Cys = 1*350e+3;               % 道床的横向阻尼  N.s/m    
    
    Par_Track.Es = 37.5e9;
    Par_Track.Br = 0.7175;                % 两股钢轨工作边的中心距之半
    Par_Track.fr = 0.35;                  % 钢轨摩擦系数
    Par_Track.Er = 207.0E9;               % 钢轨弹性模量
    Par_Track.Gr = 80.2E9;
    Par_Track.Vr = Er/2/Gr-1;
    Par_Track.Ori_prr = 0.036;
    
elseif strcmp(InpPar.Type_Track,'Flexible Track')
    % 欧洲道岔程序参数 Flexible Track
    Par_Track.RailPadProp.ky_pad = 25e6;
    Par_Track.RailPadProp.dy_pad = 10e3;
    Par_Track.RailPadProp.kz_pad = 120e6;
    Par_Track.RailPadProp.dz_pad = 25e3;
    
    Par_Track.pad_width = 0.1;
    Par_Track.RailPadProp.kyrot_pad = (Par_Track.RailPadProp.kz_pad * Par_Track.pad_width^2)/12;
    Par_Track.RailPadProp.dyrot_pad = (Par_Track.RailPadProp.dz_pad * Par_Track.pad_width^2)/12;
    
    Par_Track.BallastProp.ky_ballast = 10e6;  %Per metre sleeper length
    Par_Track.BallastProp.dy_ballast = 100e3; %Per metre sleeper length
    Par_Track.BallastProp.kz_ballast = 20e6;  %Per metre sleeper length
    Par_Track.BallastProp.dz_ballast = 200e3; %Per metre sleeper length
    
    Par_Track.CheckRailFastningProp = Par_Track.RailPadProp;
    Par_Track.CheckRailFastningProp.ky_pad = Par_Track.CheckRailFastningProp.kz_pad;
    Par_Track.CheckRailFastningProp.dy_pad = Par_Track.CheckRailFastningProp.dz_pad;
    
    Par_Track.Density_r = 7850;
    Par_Track.Density_s = 2400;
    Par_Track.Area_s = 0.054824;
    Par_Track.I22_s = 0.000224;
    
    Par_Track.Ms = Par_Track.Density_s * Par_Track.Area_s;
    
    Par_Track.Es = 37.5e9;
    Par_Track.Br = 0.7175;                % 两股钢轨工作边的中心距之半
    Par_Track.fr = 0.35;                  % 钢轨摩擦系数
    Par_Track.Er = 207.0e9;               % 钢轨弹性模量
    Par_Track.Gr = 80.2e9;
    Par_Track.Vr = Par_Track.Er/2/Par_Track.Gr-1;
    Par_Track.Ori_prr = 0.036;
end
