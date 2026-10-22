%% 利用 Bezier 曲线沿纵向插值截面
function Profile_ProCS = Get_Profile_P1_Through_CN18_250813(InpPar, j1, Par_Vehicle, Profile_ProCS, Profile_num_Interp)

%% 参数设置
Choose_Plot = 0;
Profile_ori_temp = struct('FF_Profile_num', [],'FF_Profile', [], 'FF_FrontProfile', [], 'FF_RearProfile', [], 'FF_FrontProfile_d1', [], 'FF_RearProfile_d1', [], 'FF_Radius', [], ...
                                         'FR_Profile_num', [],'FR_Profile', [], 'FR_FrontProfile', [], 'FR_RearProfile', [], 'FR_FrontProfile_d1', [], 'FR_RearProfile_d1', [], 'FR_Radius', [], ...
                                         'RF_Profile_num', [],'RF_Profile', [], 'RF_FrontProfile', [], 'RF_RearProfile', [], 'RF_FrontProfile_d1', [], 'RF_RearProfile_d1', [], 'RF_Radius', [], ...
                                         'RR_Profile_num', [],'RR_Profile', [], 'RR_FrontProfile', [], 'RR_RearProfile', [], 'RR_FrontProfile_d1', [], 'RR_RearProfile_d1', [], 'RR_Radius', []);

for i = 1:1:length(InpPar.Exp_DummyRail)
    if ismember(InpPar.Exp_DummyRail{i}, Profile_num_Interp)
        Profile_ProCS.(InpPar.Exp_DummyRail{i}) = Profile_ori_temp;
    end
end
clear Profile_ori_temp

%% L1, R1, R2, R3
for kk = 1:1:length(Profile_num_Interp)
    
    if ismember('L1', Profile_num_Interp{kk})
        Profile_ProCS.L1 = Create_prrFile(j1, InpPar, Par_Vehicle, 1, 0, InpPar.Mileage_sum.L1, InpPar.MileageInterp_Div.L1, InpPar.Profile_Bezier.L1, [1-5e-10,1,1]);
    
    elseif ismember('R1', Profile_num_Interp{kk})
        Profile_ProCS.R1 = Create_prrFile(j1, InpPar, Par_Vehicle, 1, 0, InpPar.Mileage_sum.R1, InpPar.MileageInterp_Div.R1, InpPar.Profile_Bezier.R1, [1-5e-10,1,1]);

    elseif ismember('R2', Profile_num_Interp{kk})
        % Par_RX: 拟合系数, 廓形是否需要1阶/2阶拟合(0/1), 计算所得曲率是否需要拟合(0/1), 拟合系数对应廓形里程起止范围
        Par_R2 = [1-1e-12, 1, 1, 0, 75;
                         1-5e-10, 1, 1, 75, 200];
        Profile_ProCS.R2 = Create_prrFile(j1, InpPar, Par_Vehicle, 0, 0, InpPar.Mileage_sum.R2, InpPar.MileageInterp_Div.R2, InpPar.Profile_Bezier.R2, Par_R2);                 % zjg+zgyg

    elseif ismember('R3', Profile_num_Interp{kk})
%         Profile_ProCS.R3 = Create_prrFile(j1, InpPar, Par_Vehicle, 0, 1, InpPar.Mileage_sum.R3, InpPar.MileageInterp_Div.R3, InpPar.Profile_Bezier.R3, [1-5e-9,1,1]);
        Profile_ProCS.R3 = Create_prrFile(j1, InpPar, Par_Vehicle, 0, 1, InpPar.Mileage_sum.R3, InpPar.MileageInterp_Div.R3, InpPar.Profile_Bezier.R3, [1-5e-10,1,1]);
%         Profile_ProCS.R3 = Create_prrFile(j1, InpPar, Par_Vehicle, 0, 1, InpPar.Mileage_sum.R3, InpPar.MileageInterp_Div.R3, InpPar.Profile_Bezier.R3, [1-5e-11,1,1]);
        
    end
    
end


%% 绘图对比
if Choose_Plot == 1
    % Rail Profile, Radius
    figure(31); clf
    subplot(2,2,1)
    if ~isempty(Profile_ProCS.L1.FF_Profile)
        plot(Profile_ProCS.L1.FF_FrontProfile(:,1), Profile_ProCS.L1.FF_FrontProfile(:,2), '--',...
             Profile_ProCS.L1.FF_RearProfile(:,1),  Profile_ProCS.L1.FF_RearProfile(:,2), '--',...
             Profile_ProCS.L1.FF_Profile(:,1), Profile_ProCS.L1.FF_Profile(:,2))
    end
    set(gca,'xdir','reverse'); set(gca,'ydir','reverse'); grid on
    xlabel('Y [m]');    ylabel('Z [m]');
    subplot(2,2,2)
    if ~isempty(Profile_ProCS.R1.FF_Profile)
        plot(Profile_ProCS.R1.FF_FrontProfile(:,1), Profile_ProCS.R1.FF_FrontProfile(:,2), '--',...
             Profile_ProCS.R1.FF_RearProfile(:,1),  Profile_ProCS.R1.FF_RearProfile(:,2), '--',...
             Profile_ProCS.R1.FF_Profile(:,1), Profile_ProCS.R1.FF_Profile(:,2))
    end
    if ~isempty(Profile_ProCS.R2.FF_Profile)
        plot(Profile_ProCS.R2.FF_FrontProfile(:,1), Profile_ProCS.R2.FF_FrontProfile(:,2), '--',...
             Profile_ProCS.R2.FF_RearProfile(:,1),  Profile_ProCS.R2.FF_RearProfile(:,2), '--',...
             Profile_ProCS.R2.FF_Profile(:,1), Profile_ProCS.R2.FF_Profile(:,2))
    end    
    if ~isempty(Profile_ProCS.R3.FF_Profile)
        plot(Profile_ProCS.R3.FF_FrontProfile(:,1), Profile_ProCS.R3.FF_FrontProfile(:,2), '--',...
             Profile_ProCS.R3.FF_RearProfile(:,1),  Profile_ProCS.R3.FF_RearProfile(:,2), '--',...
             Profile_ProCS.R3.FF_Profile(:,1), Profile_ProCS.R3.FF_Profile(:,2))
    end
    set(gca,'ydir','reverse'); grid on
    xlabel('Y [m]');    ylabel('Z [m]');
    
    subplot(2,2,3)
    if ~isempty(Profile_ProCS.L1.FF_Profile)
        plot(Profile_ProCS.L1.FF_Radius(:,1), Profile_ProCS.L1.FF_Radius(:,2)*1000)
    end
    set(gca,'xdir','reverse'); grid on
    xlabel('Y [m]');    ylabel('Radius [mm]');  ylim([0,500]);
    subplot(2,2,4)
    if ~isempty(Profile_ProCS.R1.FF_Profile)
        plot(Profile_ProCS.R1.FF_Radius(:,1), Profile_ProCS.R1.FF_Radius(:,2)*1000)
    end
    if ~isempty(Profile_ProCS.R2.FF_Profile)
        plot(Profile_ProCS.R2.FF_Radius(:,1), Profile_ProCS.R2.FF_Radius(:,2)*1000)
    end
    if ~isempty(Profile_ProCS.R3.FF_Profile)
        plot(Profile_ProCS.R3.FF_Radius(:,1), Profile_ProCS.R3.FF_Radius(:,2)*1000)
    end
    xlabel('Y [m]');    ylabel('Radius [mm]');  ylim([0,500]);
    grid on
    
end

if Choose_Plot==1
    figure(11); clf
    Target = RailPro_ProCS.R1.FF_Profile;
    plot(Target(:,1), Target(:,2)); hold on
    Target = RailPro_ProCS.L1.FF_Profile;
    plot(Target(:,1), Target(:,2)); hold on
    grid on
    set(gca, 'ydir', 'reverse')
end
