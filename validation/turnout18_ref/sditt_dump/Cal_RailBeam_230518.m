function InpPar = Cal_RailBeam_230518(InpPar, Choose_zjgUnEven)

% 230518: 鍦?RailBeam.Vel_Y 涓紩鍏ョ獥鍑芥暟锛屼繚璇佷袱绔钩婊戣繃娓?

clear Mileage_Defle_zgyg Mileage_Width_zjg

if isfield(InpPar, 'RailBeam')
    InpPar = rmfield(InpPar, 'RailBeam');
end

%% A.1 zgyg
% % InpPar.RailBeam.Pos_Y.R2 = [InpPar.Pos_Node.zjg_zgyg(:,2), InpPar.Pos_Node.zjg_zgyg(:,3)];
% % InpPar.RailBeam.Vel_Y.R2 = [InpPar.Pos_Node.zjg_zgyg(:,2), gradient(InpPar.Pos_Node.zjg_zgyg(:,3))./gradient(InpPar.Pos_Node.zjg_zgyg(:,2)).*InpPar.Vlc];
% 
% % M7bVI2
% % Mileage_Defle_zgyg(:,1:2) = [cell2mat(InpPar.Mileage_sum.R3(1:63,1)), sortrows([13:1:71.3, 12.5, 22.5, 68.7, 71.3]',1)];
% % Mileage_Defle_zgyg = [103.148, 0; Mileage_Defle_zgyg];
% % Mileage_Defle_zgyg(:,2) = Mileage_Defle_zgyg(:,2)*1e-3;
% % InpPar.RailBeam.Pos_Y.R2_zgyg = Mileage_Defle_zgyg;
% % InpPar.RailBeam.Vel_Y.R2_zgyg = [Mileage_Defle_zgyg(:,1), [0; gradient(Mileage_Defle_zgyg(2:end,2))./gradient(Mileage_Defle_zgyg(2:end,1)).*InpPar.Vlc]];
% % x = (InpPar.RailBeam.Vel_Y.R2_zgyg(1,1)+0.0025:0.0025:InpPar.RailBeam.Vel_Y.R2_zgyg(2,1))';
% % y = interp1(InpPar.RailBeam.Vel_Y.R2_zgyg(:,1), InpPar.RailBeam.Vel_Y.R2_zgyg(:,2), x, 'spline');
% % InpPar.RailBeam.Vel_Y.R2_zgyg = sortrows([InpPar.RailBeam.Vel_Y.R2_zgyg; x, y], 1);
% 
% % M7bVI3
% Mileage_Defle_zgyg(:,1:2) = [cell2mat(InpPar.Mileage_sum.R3(1:63,1)), sortrows([13:1:71.3, 12.5, 22.5, 68.7, 71.3]',1)];
% Mileage_Defle_zgyg = [103.148, 0; 103.176, 9.1; Mileage_Defle_zgyg];
% Mileage_Defle_zgyg(:,2) = Mileage_Defle_zgyg(:,2)*1e-3;
% InpPar.RailBeam.Pos_Y.R2_zgyg = Mileage_Defle_zgyg;
% InpPar.RailBeam.Vel_Y.R2_zgyg = [Mileage_Defle_zgyg(:,1), [0; gradient(Mileage_Defle_zgyg(2:end,2))./gradient(Mileage_Defle_zgyg(2:end,1)).*InpPar.Vlc]];
% x = (InpPar.RailBeam.Vel_Y.R2_zgyg(1,1)+0.0025:0.0025:InpPar.RailBeam.Vel_Y.R2_zgyg(2,1))';
% y = interp1(InpPar.RailBeam.Vel_Y.R2_zgyg(:,1), InpPar.RailBeam.Vel_Y.R2_zgyg(:,2), x, 'spline');
% InpPar.RailBeam.Vel_Y.R2_zgyg = sortrows([InpPar.RailBeam.Vel_Y.R2_zgyg; x, y], 1);

%%  A.2 zjg, InpPar
% zjg
if strcmp(InpPar.Choose_Turnout, '07(009)')
    Mileage_HeightRed_v0 = [0.000, 0.578, 2.889, 5.280, 6.569, 7.304, 10.962, 100.000;
                                             23.000, 14.000, 3.000, 1.375, 0.500, 0.000, 0.000, 0.000]';
elseif strcmp(InpPar.Choose_Turnout, 'CN18')
    % CN18-jg
    % Width, Height reduction value, Distance from the FSR
    % 2     16      0.485
    % 22	4.4     3.307
    % 28	2.8     4.11
    % 37.8	0.1     5.881
    % 38	0       5.913
    Mileage_HeightRed_v0 = [0.485, 3.307, 4.11, 5.881, 5.913, 100.000;
                                              16, 4.4, 2.8, 0.1, 0.000, 0.000]';
end

if Choose_zjgUnEven==1
    % 瀹炴祴灏栬建闄嶄綆鍊艰秴宸?
    xy = [0        0.9      % 灏栬建灏栫
             0.578 -0.4      % 3 mm
             2.889  1.9       % 15 mm
             7.304  1.7       % 40 mm
            10.962   0       % 71 mm
            1000      0];
    temp = interp1(xy(:,1), xy(:,2), Mileage_HeightRed_v0(:,1), 'linear');
    Mileage_HeightRed_v0(:,2) = Mileage_HeightRed_v0(:,2)+temp;
end
Mileage_HeightRed_v0(:,1) = Mileage_HeightRed_v0(:,1)+50;
Mileage_HeightRed_v0(:,2) = Mileage_HeightRed_v0(:,2)/1000;
x = (Mileage_HeightRed_v0(1,1) : 0.1 : Mileage_HeightRed_v0(end,1))';
y = interp1(Mileage_HeightRed_v0(:,1), Mileage_HeightRed_v0(:,2), x, 'linear');
InpPar.RailBeam.Pos_Z.R2_zjg = [x, y];
InpPar.RailBeam.Vel_Z.R2_zjg = [x, gradient(y)./gradient(x).*InpPar.Vlc];

% % zjg
% Mileage_Width_zjg(:,1:2) = [cell2mat(InpPar.Mileage_sum.R2(2:73,1)), sortrows([3:1:72.2, 27.4, 72.2]',1)];
% Width_RD(:,1) = [3, 15, 27.4, 35, 40, 73];
% Width_RD(:,2) = [14, 3, 1.375, 0.5, 0, 0]*1e-3;
% Mileage_Width_zjg(:,3) = interp1(Width_RD(:,1),Width_RD(:,2),Mileage_Width_zjg(:,2),'linear');
% Mileage_Width_zjg(:,4) = Mileage_Width_zjg(:,2)*1e-3-(0.016-Mileage_Width_zjg(:,3))/4;
% bools = Mileage_Width_zjg(:,2)>40;
% Mileage_Width_zjg(bools,4) = 0.0360;
% Tar = Mileage_Width_zjg(:,[1,4]);
% InpPar.RailBeam.Pos_Y.R2_zjg = Tar;
% % InpPar.RailBeam.Vel_Y.R2_zjg = [Tar(2:end,1), diff(Tar(:,2))./diff(Tar(:,1)).*InpPar.Vlc];
% InpPar.RailBeam.Vel_Y.R2_zjg = [Tar(:,1), gradient(Tar(:,2))./gradient(Tar(:,1)).*InpPar.Vlc];
% 
% % Window, InpPar
% InpPar.RailBeam.Win.R2_zjg = InpPar.RailBeam.Vel_Y.R2_zjg;
% InpPar.RailBeam.Win.R2_zjg(:,2) = 1;
% p1 = find(Mileage_Width_zjg(:,2)==35);
% p2 = find(Mileage_Width_zjg(:,2)==41);
% x1 = InpPar.RailBeam.Vel_Y.R2_zjg(p1,1);
% x2 = InpPar.RailBeam.Vel_Y.R2_zjg(p2,1);
% xx = [((x1-(x2-x1)):0.005:x2)'; x2];
% bools_del = find(diff(xx)==0);
% xx(bools_del,:) = [];
% r1 = 1;
% win_zjg = [xx, tukeywin(length(xx), r1)];
% win_zjg(xx<=x1, 2) = 1;
% 
% bools_1 = InpPar.RailBeam.Win.R2_zjg(:,1)>x2;
% InpPar.RailBeam.Win.R2_zjg(bools_1,2) = 0;
% bools_2 = InpPar.RailBeam.Win.R2_zjg(:,1)>=win_zjg(1,1) & InpPar.RailBeam.Win.R2_zjg(:,1)<=win_zjg(end,1);
% InpPar.RailBeam.Win.R2_zjg(bools_2,:) = [];
% InpPar.RailBeam.Win.R2_zjg = [InpPar.RailBeam.Win.R2_zjg; win_zjg];
% InpPar.RailBeam.Win.R2_zjg = sortrows(InpPar.RailBeam.Win.R2_zjg, 1);

%% A.3 cxg, InpPar
% Pos_Z
% if strcmp(InpPar.Choose_Turnout, '07(009)')
%     Mileage_HeightRed_v0 = [0 	53.200 	53.280 	53.360 	53.431 	53.589 	53.819 	54.123 	54.425  100
%                                               16  16.000 	13.500 	11.060 	8.870 	    4.000 	    2.900 	    1.400 	    0.000    0]';
% elseif strcmp(InpPar.Choose_Turnout, 'CN18')
%     Mileage_HeightRed_v0 = []';
% end
% Mileage_HeightRed_v0(:,1) = Mileage_HeightRed_v0(:,1)+50;
% Mileage_HeightRed_v0(:,2) = Mileage_HeightRed_v0(:,2)/1000;
% x = (Mileage_HeightRed_v0(1,1) : 0.05 : Mileage_HeightRed_v0(end,1))';
% y = interp1(Mileage_HeightRed_v0(:,1), Mileage_HeightRed_v0(:,2), x, 'linear');
% InpPar.RailBeam.Pos_Z.R3 = [x, y];
% InpPar.RailBeam.Vel_Z.R3 = [x, gradient(y)./gradient(x).*InpPar.Vlc];
% % InpPar.RailBeam.Vel_Z.R3 = [x, [0; diff(y)./diff(x).*InpPar.Vlc]];

% % cxg 鐞嗚灏栫 52.890m
% % if strcmp(T2t, 'R3') && Mileage<=50+52.890+2.170
% %     RailBeam_Motion.Pos_Y.(T2t)(i1,1) = 35.7e-3/2.170*(Mileage-50-52.890);      % 婊￠《瀹借嚦cxg鐞嗚灏栫
% %     RailBeam_Motion.Vel_Y.(T2t)(i1,1) = (71.3/2-11.0)*1e-3/(2.170-0.699)*InpPar.Vlc;
% % %     RailBeam_Motion.Vel_Y.(T2t)(i1,1) = 35.7e-3/2.170*InpPar.Vlc;
% % end
% 
% % Pos_Y, Vel_Y
% xx = 50+(52.890:0.005:52.890+2.170)';
% InpPar.RailBeam.Pos_Y.R3 = [xx, 35.7e-3/2.170*(xx-50-52.890)];
% InpPar.RailBeam.Vel_Y.R3(:,1) = xx;
% InpPar.RailBeam.Vel_Y.R3(:,2) = (71.3/2-11.0)*1e-3/(2.170-0.699)*InpPar.Vlc;
% x1 = 104.8;                         % 椤跺 63mm cxg 閲岀▼涓?04.813
% x2 = 50+52.890+2.170;
% 
% % Win
% InpPar.RailBeam.Win.R3 = InpPar.RailBeam.Vel_Y.R3;
% InpPar.RailBeam.Win.R3(:,2) = 1;
% xx = [((x1-(x2-x1)):0.005:x2)'; x2];
% bools_del = find(diff(xx)==0);
% xx(bools_del,:) = [];
% r1 = 1;
% win_cxg = [xx, tukeywin(length(xx), r1)];
% win_cxg(xx<=x1, 2) = 1;
% 
% bools_1 = InpPar.RailBeam.Win.R3(:,1)>x2;
% InpPar.RailBeam.Win.R3(bools_1,2) = 0;
% bools_2 = InpPar.RailBeam.Win.R3(:,1)>=win_cxg(1,1) & InpPar.RailBeam.Win.R3(:,1)<=win_cxg(end,1);
% InpPar.RailBeam.Win.R3(bools_2,:) = [];
% InpPar.RailBeam.Win.R3 = [InpPar.RailBeam.Win.R3; win_cxg];
% InpPar.RailBeam.Win.R3 = sortrows(InpPar.RailBeam.Win.R3, 1);

%% Check
Choose_Plot = 0;
if Choose_Plot==1
%     T2 = 'R2_zgyg';
    T2 = 'R2_zjg';
%     T2 = 'R3';

%     figure(97); clf
%     plot(win_cxg(:,1), win_cxg(:,2)); grid on

    figure(98); clf
    if isfield(InpPar.RailBeam.Win, T2)
        plot(InpPar.RailBeam.Win.(T2)(:,1), InpPar.RailBeam.Win.(T2)(:,2));
        xlabel('Mileage (m)'); ylabel('Win');
        set(gca, 'FontName', 'Times', 'FontSize', 11); grid on
    end

    figure(99); clf
    subplot(2,1,1)
    plot(InpPar.RailBeam.Pos_Y.(T2)(:,1), InpPar.RailBeam.Pos_Y.(T2)(:,2)); 
    set(gca, 'ydir', 'reverse');
    xlabel('Mileage (m)'); ylabel('Pos Y (m)');
    set(gca, 'FontName', 'Times', 'FontSize', 11); grid on

    subplot(2,1,2)
    plot(InpPar.RailBeam.Vel_Y.(T2)(:,1), InpPar.RailBeam.Vel_Y.(T2)(:,2)); hold on    
    Tar_win = InpPar.RailBeam.Win.(T2);
    win_temp = interp1(Tar_win(:,1), Tar_win(:,2), InpPar.RailBeam.Vel_Y.(T2)(:,1), 'linear');
    plot(InpPar.RailBeam.Vel_Y.(T2)(:,1), InpPar.RailBeam.Vel_Y.(T2)(:,2).*win_temp); hold on
%     plot(InpPar.RailBeam.Vel_Y.R2_zjg_ori(:,1), InpPar.RailBeam.Vel_Y.R2_zjg_ori(:,2)); hold on    
    xlabel('Mileage (m)'); ylabel('Vel Y (m/s)');
    set(gca, 'FontName', 'Times', 'FontSize', 11); grid on; 

end

%% Draft
% Fit
% InpPar.RailBeam.Vel_Y.R2_zjg_ori = InpPar.RailBeam.Vel_Y.R2_zjg;
% p1 = find(Mileage_Width_zjg(:,2)==35);
% p2 = find(Mileage_Width_zjg(:,2)==40);
% x1 = InpPar.RailBeam.Vel_Y.R2_zjg(p1+1,1);
% x2 = InpPar.RailBeam.Vel_Y.R2_zjg(p2,1);
% xx = (x1:0.005:x2)';
% InpPar.RailBeam.Vel_Y.R2_zjg(p1+1:p2,:) = [];
% yy = interp1(InpPar.RailBeam.Vel_Y.R2_zjg(:,1), InpPar.RailBeam.Vel_Y.R2_zjg(:,2), xx, 'spline');
% InpPar.RailBeam.Vel_Y.R2_zjg = sortrows([InpPar.RailBeam.Vel_Y.R2_zjg; xx, yy],1);

%% Draft
% RailBeam Motion
% load RailBeam.mat
% HR_r.zjg_zgyg(:,1) = [0, 0.578, 2.889, 5.28, 6.569, 7.304, 100];
% HR_r.zjg_zgyg(:,2) = [23, 14, 3, 1.375, 0.5, 0, 0]*1e-3;
% HR_r.cxg(:,1) = [53.200, 53.280, 53.360, 53.431, 53.589, 53.819, 54.123, 54.425, 54.724, 100];
% HR_r.cxg(:,2) = [16.000, 13.500, 11.060, 8.870, 4.000, 2.900, 1.400, 0.000, 0.000, 0.000]*1e-3;
% % M5b
% HR_r.zjg_zgyg(:,2) = HR_r.zjg_zgyg(:,2)*0;
% HR_r.cxg(:,2) = HR_r.cxg(:,2)*0;
% RailBeam = Cal_RailDeflection(HR_r);
% 
% if Choose_Plot==1
%     figure(40); clf
%     Target_1 = RailBeam.Pos_Y;         Target_2 = RailBeam.Vel_Y;
%     Target_3 = RailBeam.Pos_Yaw;    Target_4 = RailBeam.Vel_Yaw;
% %     Target_1 = RailBeam.Pos_Z;           Target_2 = RailBeam.Vel_Z;
% %     Target_3 = RailBeam.Pos_Pitch;    Target_4 = RailBeam.Vel_Pitch;
%     for i1 = 1:1:length(Type_Rail)
%         T1 = Type_Rail{i1};
%         subplot(2,2,1)
%         plot(Target_1.(T1)(:,1)-50, Target_1.(T1)(:,2)); hold on; ylabel('Pos Y / Z (m)')
%         subplot(2,2,2)
%         plot(Target_2.(T1)(:,1)-50, Target_2.(T1)(:,2)); hold on; ylabel('Vel Y / Z (m/s)')
%         subplot(2,2,3)
%         plot(Target_3.(T1)(:,1)-50, Target_3.(T1)(:,2)); hold on; ylabel('Pos Yaw / Pitch (m)')
%         subplot(2,2,4)
%         plot(Target_4.(T1)(:,1)-50, Target_4.(T1)(:,2)); hold on; ylabel('Vel Yaw / Pitch (m/s)')
%     end
%     for kk = 1:1:4
%         subplot(2,2, kk)
%         if kk==1
%             legend(Type_Rail, 'Interpreter', 'none', 'Position',[0.2649 0.9433 0.4643 0.0440], 'Orientation','horizontal', 'FontName', 'Times');
%         end
%         set(gca, 'FontName', 'Times');  grid on
%         xlim([-5, 65]);
% %         xlim([-5, 25]);
%     end
% end

