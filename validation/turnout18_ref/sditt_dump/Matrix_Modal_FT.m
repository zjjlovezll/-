%% 基于模态叠加法，构建 M_track, K_track, C_track
function [M_track, K_track, C_track, NM_FT, NM_FT_start] = Matrix_Modal_FT(Mass_Rail_Free, Stiff_Rail_Free, Damp_Rail_Free, ModeFreq_Rail, ModeShape_Rail, ...
          Pos_Node, N_Node_Rail, NM_Rail, DOF_Rail, Par_Track, Type_Rail)

clear Mass_Rail Stiffness_Rail Damping_Rail Damping_Rail
Mass_Rail = Mass_Rail_Free;
Stiff_Rail = Stiff_Rail_Free;
Damp_Rail = Damp_Rail_Free;
Choose_Validate = 0;

%% 1. 计算约束刚度、阻尼矩阵 Stiffness_Rail, Damping_Rail
for i = 1:3:4
    % Constructing the mass, stiffness and damping matrices with constraints   
    j_max = eval(['N_Node_Rail.',Type_Rail{i}]);
    for j = 1:4:j_max
        MatPos_Fastener_x = (j-1)*6+1;
        MatPos_Fastener_y = (j-1)*6+2;
        MatPos_Fastener_z = (j-1)*6+3;
               
        eval(['Stiffness_Rail.',Type_Rail{i},'(MatPos_Fastener_x, MatPos_Fastener_x) = Stiffness_Rail.',Type_Rail{i},'(MatPos_Fastener_x, MatPos_Fastener_x) + Par_Track.',Type_Rail{i},'_FasterenStiff(1);']);
        eval(['Stiffness_Rail.',Type_Rail{i},'(MatPos_Fastener_y, MatPos_Fastener_y) = Stiffness_Rail.',Type_Rail{i},'(MatPos_Fastener_y, MatPos_Fastener_y) + Par_Track.',Type_Rail{i},'_FasterenStiff(2);']);
        eval(['Stiffness_Rail.',Type_Rail{i},'(MatPos_Fastener_z, MatPos_Fastener_z) = Stiffness_Rail.',Type_Rail{i},'(MatPos_Fastener_z, MatPos_Fastener_z) + Par_Track.',Type_Rail{i},'_FasterenStiff(3);']);        
        eval(['Damping_Rail.',Type_Rail{i},'(MatPos_Fastener_x, MatPos_Fastener_x) = Damping_Rail.',Type_Rail{i},'(MatPos_Fastener_x, MatPos_Fastener_x) + Par_Track.',Type_Rail{i},'_FasterenDamp(1);']);
        eval(['Damping_Rail.',Type_Rail{i},'(MatPos_Fastener_y, MatPos_Fastener_y) = Damping_Rail.',Type_Rail{i},'(MatPos_Fastener_y, MatPos_Fastener_y) + Par_Track.',Type_Rail{i},'_FasterenDamp(2);']);
        eval(['Damping_Rail.',Type_Rail{i},'(MatPos_Fastener_z, MatPos_Fastener_z) = Damping_Rail.',Type_Rail{i},'(MatPos_Fastener_z, MatPos_Fastener_z) + Par_Track.',Type_Rail{i},'_FasterenDamp(3);']);
    end
       
    % Validate generalized stiffness and mass matrices
    if Choose_Validate == 1
        Stiff_temp = Stiff_Rail.zjbg - Stiff_Rail_Free.zjbg;
        Stiff_temp = Stiff_Rail.qjbg - Stiff_Rail_Free.qjbg;
        clear output_Nor
        for p = 1:1:NM_Rail.zjbg
            output_Nor(p,1) = (ModeShape_Rail.qjbg(:,p))' * Mass_Rail.qjbg * ModeShape_Rail.qjbg(:,p);
            output_Nor(p,2) = (ModeShape_Rail.qjbg(:,p))' * Stiff_Rail.qjbg * ModeShape_Rail.qjbg(:,p);
            output_Nor(p,3) = (2*pi*ModeFreq_Rail.qjbg(p,2))^2*output_Nor(p,1)/output_Nor(p,2);
        end        
        Mass_Rail_Gen.qjbg = (ModeShape_Rail.qjbg)' * Mass_Rail.qjbg * ModeShape_Rail.qjbg;
        
        figure(1); clf
        plot(1:1:NM_Rail.zjbg, output_Nor(:,1), 1:1:NM_Rail.zjbg, output_Nor(:,3));	grid on
    end
end

%% 2. Generalized stiffness and mass matrices: Mass_Rail_Gen, Stiffness_Rail_Gen, Damping_Rail_Gen
Mass_Rail_Gen.zjbg = (ModeShape_Rail.zjbg)' * Mass_Rail.zjbg * ModeShape_Rail.zjbg;
Mass_Rail_Gen.qjbg = (ModeShape_Rail.qjbg)' * Mass_Rail.qjbg * ModeShape_Rail.qjbg;

Stiffness_Rail_Gen.zjbg = (ModeShape_Rail.zjbg)' * Stiff_Rail.zjbg * ModeShape_Rail.zjbg;
Stiffness_Rail_Gen.qjbg = (ModeShape_Rail.qjbg)' * Stiff_Rail.qjbg * ModeShape_Rail.qjbg;

Damping_Rail_Gen.zjbg = (ModeShape_Rail.zjbg)' * Damp_Rail.zjbg * ModeShape_Rail.zjbg;
Damping_Rail_Gen.qjbg = (ModeShape_Rail.qjbg)' * Damp_Rail.qjbg * ModeShape_Rail.qjbg;

% d_temp = Mass_Rail_Gen.zjbg-eye(length(Mass_Rail_Gen.zjbg));
% max(max(d_temp))
% Stiffness_zjbg_temp = diag((2*pi*ModeFreq_Rail.zjbg(:,2)).^2);
% d_temp = Stiffness_Rail_Gen.zjbg-Stiffness_zjbg_temp;
% [a, row] = max(d_temp);
% [b, col] = max(max(d_temp));

NM_FT = 0;
for i = 1:3:4
    NM_FT = NM_FT + eval(['NM_Rail.',Type_Rail{i}]);
end
NM_FT_start = [0; ...
               NM_Rail.zjbg; ...
               NM_Rail.zjbg; ...
               NM_Rail.zjbg; ...
               NM_Rail.zjbg+NM_Rail.qjbg];

M_track = eye(NM_FT, NM_FT);
K_track = zeros(NM_FT, NM_FT);
C_track = zeros(NM_FT, NM_FT);
for i = 1:3:4
%     K_track(m:n,m:n) = diag((2*pi*ModeFreq_Rail.qjbg(:,2)).^2);    
    m = NM_FT_start(i)+1;
    n = NM_FT_start(i+1);
    K_track(m:n,m:n) = eval(['diag((2*pi*ModeFreq_Rail.', Type_Rail{i}, '(:,2)).^2)']);
    C_track(m:n,m:n) = eval(['Damping_Rail_Gen.', Type_Rail{i}]);
end

