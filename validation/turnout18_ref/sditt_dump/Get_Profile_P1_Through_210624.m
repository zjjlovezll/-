%% 利用 Bezier 曲线沿纵向插值截面
function Profile_ProCS = Get_Profile_P1_Through_210624(InpPar, j1, Par_Vehicle, Profile_ProCS, Profile_num_Interp)

% global InpPar.Mileage_sum InpPar.Profile_Bezier InpPar.MileageInterp_Div
% global InpPar.Exp_WS InpPar.Exp_DummyRail

% TEST
% Profile_ProCS = RailPro_ProCS;
% Profile_num_Interp = {'R2', 'R3'};

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
        % L1: zjbg
        for i11 = 1:1:4
            profile_L1_num = 1;
            filename_profile = InpPar.Mileage_sum.R1{1,2};
            % Revision !!!!!!
%             filename_profile = 'zjbg_LinFen_3#.txt';
%             filename_profile = 'zjbg_LinFen_1#.txt';
            profile_r_ori_L1  = load(filename_profile);
            profile_r_ori_Front_L1 = profile_r_ori_L1;
            profile_r_ori_Rear_L1 = profile_r_ori_L1;
%             profile_r_ori_L1_Radius = Radius_profile_v3(profile_r_ori_L1,1-1e-11,1,1);

            % LinFen
%             profile_r_ori_L1_Radius = Radius_profile_v3(profile_r_ori_L1,1-5e-9,1,1);

            % LinFen_1#
            profile_r_ori_L1_Radius = Radius_profile_v3(profile_r_ori_L1,1-5e-8,1,1);

            profile_r_ori_L1_Radius(:,2) = abs(profile_r_ori_L1_Radius(:,2));
            [~,~,profile_r_ori_Front_L1_d1,~] = Extreme_point(profile_r_ori_Front_L1);
            [~,~,profile_r_ori_Rear_L1_d1,~] = Extreme_point(profile_r_ori_Rear_L1);            
            Profile_ProCS.L1.([InpPar.Exp_WS{i11},'_Profile_num']) = profile_L1_num;
            Profile_ProCS.L1.([InpPar.Exp_WS{i11},'_Profile']) = profile_r_ori_L1;
            Profile_ProCS.L1.([InpPar.Exp_WS{i11},'_FrontProfile']) = profile_r_ori_Front_L1;
            Profile_ProCS.L1.([InpPar.Exp_WS{i11},'_RearProfile'])  = profile_r_ori_Rear_L1;
            Profile_ProCS.L1.([InpPar.Exp_WS{i11},'_FrontProfile_d1']) = profile_r_ori_Front_L1_d1;
            Profile_ProCS.L1.([InpPar.Exp_WS{i11},'_RearProfile_d1'])  = profile_r_ori_Rear_L1_d1;
            Profile_ProCS.L1.([InpPar.Exp_WS{i11},'_Radius']) = profile_r_ori_L1_Radius;
        end        
        if Choose_Plot == 1
            figure(20); clf
            subplot(2,1,1)
            plot(profile_r_ori_L1(:,1),profile_r_ori_L1(:,2));
            set(gca,'ydir','reverse');    grid on;
            subplot(2,1,2)
            plot(profile_r_ori_L1_Radius(:,1),profile_r_ori_L1_Radius(:,2));
            grid on
        end
    
    elseif ismember('R1', Profile_num_Interp{kk})
        % R1, R2, R3: qjbg, zjg_zgyg, cxg
        % InpPar.Profile_Bezier, Profile_ProCS
        % Profile_ori = Create_prrFile(j1, InpPar, Par_Vehicle, IF_SameFrontProf, IF_SameRearProf, InpPar.Mileage_sum_Target, InpPar.MileageInterp_Div_Target, InpPar.Profile_Bezier_Target, Par_RailPro_Fit)
%         Profile_ProCS.R1 = Create_prrFile(j1, InpPar, Par_Vehicle, 1, 0, InpPar.Mileage_sum.R1, InpPar.MileageInterp_Div.R1, InpPar.Profile_Bezier.R1, [1-1e-11,1,1]);

%         Profile_ProCS.R1 = Create_prrFile(j1, InpPar, Par_Vehicle, 1, 0, InpPar.Mileage_sum.R1, InpPar.MileageInterp_Div.R1, InpPar.Profile_Bezier.R1, [1-5e-9,1,1]);
        % LinFen_1#
        Profile_ProCS.R1 = Create_prrFile(j1, InpPar, Par_Vehicle, 1, 0, InpPar.Mileage_sum.R1, InpPar.MileageInterp_Div.R1, InpPar.Profile_Bezier.R1, [1-5e-8,1,1]);

    elseif ismember('R2', Profile_num_Interp{kk})
        % Par_RX: 拟合系数, 廓形是否需要1阶/2阶拟合(0/1), 计算所得曲率是否需要拟合(0/1), 拟合系数对应廓形里程起止范围
%         Par_R2 = [1-1e-12, 1, 1, 0, 75;
%                          1-5e-10, 1, 1, 75, 200];
        Par_R2 = [1-1e-11, 1, 1, 0, 75;
                        1-5e-10, 1, 1, 75, 200];
        Profile_ProCS.R2 = Create_prrFile(j1, InpPar, Par_Vehicle, 0, 0, InpPar.Mileage_sum.R2, InpPar.MileageInterp_Div.R2, InpPar.Profile_Bezier.R2, Par_R2);                 % zjg+zgyg

    elseif ismember('R3', Profile_num_Interp{kk})
%         Profile_ProCS.R3 = Create_prrFile(j1, InpPar, Par_Vehicle, 0, 1, InpPar.Mileage_sum.R3, InpPar.MileageInterp_Div.R3, InpPar.Profile_Bezier.R3, [1-5e-7,1,1]);
        Profile_ProCS.R3 = Create_prrFile(j1, InpPar, Par_Vehicle, 0, 1, InpPar.Mileage_sum.R3, InpPar.MileageInterp_Div.R3, InpPar.Profile_Bezier.R3, [1-5e-9,1,1]);  % 默认
%         Profile_ProCS.R3 = Create_prrFile(j1, InpPar, Par_Vehicle, 0, 1, InpPar.Mileage_sum.R3, InpPar.MileageInterp_Div.R3, InpPar.Profile_Bezier.R3, [1-5e-10,1,1]);
%         Profile_ProCS.R3 = Create_prrFile(j1, InpPar, Par_Vehicle, 0, 1, InpPar.Mileage_sum.R3, InpPar.MileageInterp_Div.R3, InpPar.Profile_Bezier.R3, [1-5e-11,1,1]);
%         Profile_ProCS.R3 = Create_prrFile(j1, InpPar, Par_Vehicle, 0, 1, InpPar.Mileage_sum.R3, InpPar.MileageInterp_Div.R3, InpPar.Profile_Bezier.R3, [1-5e-12,1,1]);
        
    end
    
end


%% Plain Track
% if ismember('R1', Profile_num_Interp)
%     Profile_ProCS.R1 = Profile_ProCS.L1;
% end

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
