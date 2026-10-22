%% 导入柔性轮对的模态文件，并确定轮轴、踏面基点、计算侧滚角点等关键节点

function Load_ModeShape_FW(CutFreq_FW)

global Pos_Node ModeFreq ModeShape N_Node NM_FW Par_Vehicle Par_FW

% clc
% clear

addpath('E:\# Flex-Rigid-20200418\# FW_Rotation\ANSYS_FW_SDITT_220608_Mass21\Modes_RigidBeam_Mass21_6DOF_NRC_230506')

% NM = 53-6;
NM_del = 6;
Choose_Check = 0;
Choose_Plot = 0;
% CutFreq_FW = 2200;

Par_Vehicle.Dlb = 1.353/2;
Par_Vehicle.Drc = 0.07;
Par_Vehicle.R0 = 0.43;

%% 1a. 导入数据 
% 导入节点坐标
fid = fopen('NodePos_FW_SDITT_MASS21_220608.txt');
pos_node_ori = textscan(fid,'%f %f %f %f %f %f %f','HeaderLines',0,'Delimiter',' ','MultipleDelimsAsOne',1,'CommentStyle','   NODE');
fclose(fid);
Pos_Node.FW = [pos_node_ori{1,1} pos_node_ori{1,2} pos_node_ori{1,3} pos_node_ori{1,4}];
N_Node.FW = size(Pos_Node.FW, 1);

%% 1b. Ele_List
fid = fopen('ELIST.lis');
ELIST_ori = textscan(fid, repmat('%f ', 1, 14), 'HeaderLines', 5, 'CommentStyle', '    ELEM');
fclose(fid);
Ele_List = [ELIST_ori{1,1} ELIST_ori{1,7} ELIST_ori{1,8} ELIST_ori{1,9} ELIST_ori{1,10} ELIST_ori{1,11} ELIST_ori{1,12} ELIST_ori{1,13} ELIST_ori{1,14}];

%% 2. 导入矩阵: Mass_FW, Stiff_FW
if Choose_Check == 1
    [Mass_FW.Free, Mass_FW.Free_Mapping, DOF_FW.Free] = Load_HBFILE('HBFILE_FW_Free_MASS');
    [Stiff_FW.Free, Stiff_FW.Free_Mapping, DOF_FW.Free] = Load_HBFILE('HBFILE_FW_Free_STIFF');
else
     [Mass_FW.Free_Mapping, DOF_FW.Free] = Load_HBFILE_Mapping('HBFILE_FW_Free_MASS');
     [Stiff_FW.Free_Mapping,   DOF_FW.Free] = Load_HBFILE_Mapping('HBFILE_FW_Free_STIFF');
end

% 计算 Mass21 DOF 在 ModeShape 中的位置
Range_ROT = [];
for i = 1:1:DOF_FW.Free
    if strcmp(Mass_FW.Free_Mapping{i,3}, 'ROTX')
        Range_ROT = [Range_ROT; i];
    end
end

%% 3. 导入振型矩阵 ModeFreq, ModeShape
% 导入振型与频率之间的关系文件
fid = fopen('Modefile_FW_SDITT_220608_MASS21_FreqModal.txt');
frequency_modeshape = textscan(fid, '%f %f %f','HeaderLines',0);
fclose(fid);
ModeFreq.FW_All = [frequency_modeshape{1,1} frequency_modeshape{1,2} frequency_modeshape{1,3}];
ModeFreq.FW_All(1:NM_del,:) = [];
ModeFreq.FW_All(:,1) = ModeFreq.FW_All(:,1)-NM_del;
NM_FW_All = length(ModeFreq.FW_All(:,1));

bools = ModeFreq.FW_All(:,2)<=CutFreq_FW;
ModeFreq.FW = ModeFreq.FW_All(bools,:);
NM_FW = length(find(bools));

%%% 确定第k阶 Modeshape 矩阵(N*1)元素位置与 Modefile 文件中振型结果位置的映射关系
fid = fopen('Modefile_FW_SDITT_220608_MASS21_Mode30.txt');
temp = textscan(fid, repmat(' %f',1,7), 'HeaderLines',1);
fclose(fid);
Modefile_temp = [temp{1},temp{2},temp{3},temp{4},temp{5},temp{6},temp{7}];

%%% 构造 Target_Mapping 中每行元素与振型文件对应自由度的位置关系
Target = Mass_FW.Free_Mapping;
for i = 1:1:DOF_FW.Free
    pos = find(Modefile_temp(:,1)==Target{i,2});
    if strcmp(Target{i,3}, 'UX')
        ModeShape.Modefile_Mapping_FW(i,1) = pos+size(Modefile_temp,1)*1;
    elseif strcmp(Target{i,3}, 'UY')
        ModeShape.Modefile_Mapping_FW(i,1) = pos+size(Modefile_temp,1)*2;
    elseif strcmp(Target{i,3}, 'UZ')
        ModeShape.Modefile_Mapping_FW(i,1) = pos+size(Modefile_temp,1)*3;
    elseif strcmp(Target{i,3}, 'ROTX')
        ModeShape.Modefile_Mapping_FW(i,1) = pos+size(Modefile_temp,1)*4;
    elseif strcmp(Target{i,3}, 'ROTY')
        ModeShape.Modefile_Mapping_FW(i,1) = pos+size(Modefile_temp,1)*5;
    else
        ModeShape.Modefile_Mapping_FW(i,1) = pos+size(Modefile_temp,1)*6;
    end
end

%%% 振型文件 ModeShape
ModeShape.FW_All = zeros(DOF_FW.Free, NM_FW_All);
for j = 1:1:NM_FW_All
    fid = fopen(['Modefile_FW_SDITT_220608_MASS21_Mode',num2str(j+NM_del),'.txt']);
    temp = textscan(fid, repmat(' %f',1,7), 'HeaderLines',1);
    fclose(fid);
    Modefile_temp = [temp{1},temp{2},temp{3},temp{4},temp{5},temp{6},temp{7}];    
    for i = 1:1:DOF_FW.Free
        pos = ModeShape.Modefile_Mapping_FW(i,1);
        ModeShape.FW_All(i,j) = Modefile_temp(pos);
    end
end
bools = ModeFreq.FW_All(:,2)<=CutFreq_FW;
ModeShape.FW = ModeShape.FW_All(:,bools);

%% 0.1 Generalized Mass and Stiffness, ModeShape, ModeFreq
%%% Mass_Rail, Stiff_Rail, Damp_Rail, Pos_Node, N_Node, DOF_Rail, NM_Rail, ModeFreq, ModeShape
if Choose_Check == 1
    clear output_Nor
    for p = 1:1:NM_FW_All
        output_Nor(p,1) = (ModeShape.FW_All(:,p))' * Mass_FW.Free * ModeShape.FW_All(:,p);
        output_Nor(p,2) = (ModeShape.FW_All(:,p))' * Stiff_FW.Free * ModeShape.FW_All(:,p);
        output_Nor(p,3) = (2*pi*ModeFreq.FW_All(p,2))^2*output_Nor(p,1)/output_Nor(p,2);
    end
    
    len = 1:1:NM_FW_All;
    Mass_Generalized = (ModeShape.FW_All)' * Mass_FW.Free * ModeShape.FW_All;
    for i = 1:1:length(Mass_Generalized)
        Mass_Generalized(i,i) = 0;
    end
    min(min(Mass_Generalized))
    max(max(Mass_Generalized))
    
    figure(1); clf
    plot(len, output_Nor(:,1), len, output_Nor(:,3));
    grid on
end

%% 2.选取主要节点, Par_FW
%%% (1)轴箱悬挂节点
% 寻找左右两侧一系悬挂、名义滚动圆对应的节点编号和行数
lim = 1e-10;
y_NRC = Par_Vehicle.Dlb+Par_Vehicle.Drc;
z_NRC = Par_Vehicle.R0;
Type_Pos = {'AxleBox_L', 'AxleBox_R', 'NRC_L', 'NRC_R'};
Pos_Y = [-1, 1, -y_NRC, y_NRC];
Pos_Z = [0, 0, z_NRC, z_NRC];

Target = Mass_FW.Free_Mapping;
for i = 1:1:length(Type_Pos)
    bools = abs(Pos_Node.FW(:,2)-0)<lim & abs(Pos_Node.FW(:,3)-Pos_Y(i))<lim & abs(Pos_Node.FW(:,4)-Pos_Z(i))<lim;
    Par_FW.PosNode_pos.(Type_Pos{i}) = find( bools );
    num_Node = Pos_Node.FW(bools,1);   
    Par_FW.DOF_pos.(Type_Pos{i}) = [ find(cell2mat(Target(:,2))==num_Node & strcmp(Target(:,3), 'UX')), ...
                                                                  find(cell2mat(Target(:,2))==num_Node & strcmp(Target(:,3), 'UY')), ...
                                                                  find(cell2mat(Target(:,2))==num_Node & strcmp(Target(:,3), 'UZ'))];
    Pos_Node.(Type_Pos{i}) = [0, Pos_Y(i), Pos_Z(i)];
end

%%% (2)轮对踏面基点
% Right Side
%     NODE        X            Y            Z          THXY     THYZ     THZX
%         9 -0.42223      0.67650     -0.10342E-15     0.00     0.00     0.00
%        32 -0.42223      0.81150     -0.10342E-15     0.00     0.00     0.00
% Left Side
%       333 -0.42223     -0.67650       0.0000         0.00     0.00     0.00
%       356 -0.42223     -0.81150       0.0000         0.00     0.00     0.00
lim = 1e-5;
Type_Pos = {'WBack_R', 'WOut_R', 'WBack_L', 'WOut_L'};
Pos_Y = [Par_Vehicle.Dlb, Par_Vehicle.Dlb+0.135, -Par_Vehicle.Dlb, -Par_Vehicle.Dlb-0.135];
Pos_Z = [0.436619, 0.42223, 0.436619, 0.42223];     % FW_SDITT_230506_Mass21_v2.mat  
% Pos_Z = [0.42223, 0.42223, 0.42223, 0.42223];     % FW_SDITT_230506_Mass21.mat  

Target = Mass_FW.Free_Mapping;
for i = 1:1:length(Type_Pos)
    bools = abs(Pos_Node.FW(:,2)-0)<lim & abs(Pos_Node.FW(:,3)-Pos_Y(i))<lim & abs(Pos_Node.FW(:,4)-Pos_Z(i))<lim;
    Par_FW.PosNode_pos.(Type_Pos{i}) = find( bools );
    num_Node = Pos_Node.FW(bools,1);   
    Par_FW.DOF_pos.(Type_Pos{i}) = [ find(cell2mat(Target(:,2))==num_Node & strcmp(Target(:,3), 'UX')), ...
                                                                  find(cell2mat(Target(:,2))==num_Node & strcmp(Target(:,3), 'UY')), ...
                                                                  find(cell2mat(Target(:,2))==num_Node & strcmp(Target(:,3), 'UZ'))];
    Pos_Node.(Type_Pos{i}) = [0, Pos_Y(i), Pos_Z(i)];
end

%%% (3)选取踏面周围节点, Par_FW
%%% 踏面节点横向坐标
fid = fopen('NLIST_Trend_Lat.lis');
pos_node_ori = textscan(fid, '%f %f %f %f %f %f %f', 'HeaderLines', 4, 'Delimiter', ' ', 'MultipleDelimsAsOne', 1, 'CommentStyle', '   NODE');
fclose(fid);
pos_tread_Y = pos_node_ori{1,3};
Par_FW.pos_tread_Y = sortrows(pos_tread_Y,1);
bools = Par_FW.pos_tread_Y>0;
Par_FW.pos_tread_Y_L = Par_FW.pos_tread_Y(~bools);
Par_FW.pos_tread_Y_R = Par_FW.pos_tread_Y(bools);

%%% pos_Node_Cylindrical: Node_num, Theta, Rho, Z, pos_Node
Par_FW.Cartesian = Pos_Node.FW;
[theta, rho, z] = cart2pol(Par_FW.Cartesian(:,2), Par_FW.Cartesian(:,4), Par_FW.Cartesian(:,3));
Par_FW.Cylindrical = [Par_FW.Cartesian(:,1), theta, rho, z];

if Choose_Plot == 1
    figure(1); clf
    bools_1 = theta > (90-7)/180*pi & theta < (90+7)/180*pi;
    plot3(Par_FW.Cartesian(bools_1,2), Par_FW.Cartesian(bools_1,3), Par_FW.Cartesian(bools_1,4), '+','LineWidth',0.005);
    grid on;    view([70,35]);
    set(gca,'zdir','reverse');  xlabel('X(m)'); ylabel('Y(m)'); zlabel('Z(m)');
end

% bools, Par_FW
clear bools
bools.tread_1 = (theta>=(90-1)/180*pi & theta<=(90+1)/180*pi);
bools.tread_2 = (theta>=(90-16)/180*pi & theta<=(90-14)/180*pi);
bools.tread_3 = (theta>=(90+14)/180*pi & theta<=(90+16)/180*pi);
Type_Pos_i = {'Mid', 'Front', 'Rear'};
Type_Side = {'L', 'R'};
for i = 1:1:3                   % 'Mid', 'Front', 'Rear'
%     pos_tread_temp = Par_FW.Cartesian(bools.(['tread_',num2str(i)]), :);      % Cartesian
    pos_tread_temp = Par_FW.Cylindrical(bools.(['tread_',num2str(i)]), :);       % Cylindrical
    for j1 = 1:1:2             % 'L', 'R'
        T1 = ['Tread_', Type_Side{j1}, '_', Type_Pos_i{i}];
        Target_Y = Par_FW.(['pos_tread_Y_', Type_Side{j1}]);

        % j2 = length(Target_Y)
        for j2 = 1:1:length(Target_Y)
%             bools_Y = abs(pos_tread_temp(:,3)-Target_Y(j2))<1e-5;       % Cartesian
            bools_Y = abs(pos_tread_temp(:,4)-Target_Y(j2))<1e-5;       % Cylindrical
            pos_tread_Y = pos_tread_temp(bools_Y,:);
            if (j1==1&&j2==length(Target_Y)) || (j1==2&&j2==1)
%                 [~,pos] = min(abs(pos_tread_Y(:,4)-0.42223));     % Cartesian
                [~,pos] = min(abs(pos_tread_Y(:,3)-0.42223));          % Cylindrical
            else
%                 [~,pos] = max(pos_tread_Y(:,4));                          % Cartesian
                [~,pos] = max(pos_tread_Y(:,3));                                % Cylindrical
            end
            pos_tread_Y = pos_tread_Y(pos,:);
            num_Node = pos_tread_Y(1);
%             Par_FW.(T1)(j2,:) = pos_tread_Y;                      % Cartesian
            bools_2 = Pos_Node.FW(:,1)==num_Node;
            Par_FW.(T1)(j2,:) = Pos_Node.FW(bools_2,:);
            Par_FW.DOF_pos.(T1)(j2,:) = ...
                [ find(cell2mat(Target(:,2))==num_Node & strcmp(Target(:,3), 'UX')), ...
                  find(cell2mat(Target(:,2))==num_Node & strcmp(Target(:,3), 'UY')), ...
                  find(cell2mat(Target(:,2))==num_Node & strcmp(Target(:,3), 'UZ'))];
        end

    end
end
Par_FW .Tread_Mid = [Par_FW.Tread_L_Mid; Par_FW.Tread_R_Mid];
Par_FW.DOF_pos.Tread_Mid = [Par_FW.DOF_pos.Tread_L_Mid; Par_FW.DOF_pos.Tread_R_Mid];
                           
if Choose_Plot == 1
    figure(1); clf
    plot3(Par_FW.Tread(:,2), Par_FW.Tread(:,3), Par_FW.Tread(:,4), '+','LineWidth',0.005);
    grid on;    view([70,35]);
    set(gca,'zdir','reverse');  xlabel('X(m)'); ylabel('Y(m)'); zlabel('Z(m)');
    
    pos_tread_Cartesian = [pos_tread_Cartesian_1; NaN(1,4); pos_tread_Cartesian_2; NaN(1,4); pos_tread_Cartesian_3];
    X = pos_tread_Cartesian(:,2);
    Y = pos_tread_Cartesian(:,3);
    Z = pos_tread_Cartesian(:,4);
    figure(2); clf
    plot3(X,Y,Z);
    bools = isnan(X(:,1));
    X(bools,:) = [];
    Y(bools,:) = [];
    Z(bools,:) = [];
    tri = delaunay(X,Y);
    trimesh(tri, X, Y, Z);
    grid on;    view([70,35]);
    set(gca,'zdir','reverse');  xlabel('X(m)'); ylabel('Y(m)'); zlabel('Z(m)');
    shading interp;
end

%%% (4) 构造 Mid Tread 的振型矩阵, ModeShape
Type_Result = {'Tread_Mid', 'Tread_L_Mid', 'Tread_R_Mid'};
for i = 1:1:length(Type_Result)
    Target = Par_FW.DOF_pos.(Type_Result{i});
    ModeShape.(Type_Result{i}) = [];
    for j = 1:1:size(Target,1)
        bools = Target(j,1:3)';
        ModeShape.(Type_Result{i}) = [ModeShape.(Type_Result{i}); ModeShape.FW(bools,:)];
    end
end

% save FW_SDITT_230506_Mass21.mat Pos_Node Mass_FW Stiff_FW DOF_FW NM_FW ModeFreq ModeShape Ele_List Par_FW
save FW_SDITT_230506_Mass21_v2.mat Pos_Node Mass_FW Stiff_FW DOF_FW NM_FW ModeFreq ModeShape Ele_List Par_FW

